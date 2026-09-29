"""BPMN 2.0: AS-IS **descoberto do log** (via DFG) e TO-BE desenhado, ambos com diagrama (DI).

Correção de rota: a versão anterior tinha o AS-IS hardcoded e sem diagrama — o modelo não vinha do
log e não abria visualmente. Agora:
- AS-IS: atividades e arestas vêm do DFG descoberto (`reports/dfg.json`/`reports/mining.json`);
  onde o log mostra ramificação (>1 aresta de saída) entra um `exclusiveGateway`, e cada aresta é
  anotada com a frequência observada.
- TO-BE: desenhado (é decisão de projeto, não descoberta) com `serviceTask` para as etapas automatizadas.
- Ambos ganham **BPMN DI** (BPMNDiagram/BPMNPlane/BPMNShape/BPMNEdge) para abrir em bpmn.io/Camunda.
- `validate_bpmn` checa ids, refs de fluxo, start/end e integridade do DI.

Uso: python -m src.bpmn [--mining reports/mining.json] [--outdir bpmn]
"""
from __future__ import annotations

import argparse
import json
import os
import xml.etree.ElementTree as ET

BPMN_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"
BPMNDI_NS = "http://www.omg.org/spec/BPMN/20100524/DI"
OMGDC_NS = "http://www.omg.org/spec/DD/20100524/DC"
OMGDI_NS = "http://www.omg.org/spec/DD/20100524/DI"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"

TO_BE_NODES = [
    ("start", "Recebimento do documento", "event"),
    ("extracao", "Extração automática (API)", "service"),
    ("validacao", "Validação por regras (automática)", "service"),
    ("gateway_div", "Divergência?", "gateway"),
    ("conferencia", "Conferência humana (exceção)", "user"),
    ("correcao", "Correção", "user"),
    ("aprovacao", "Aprovação humana", "user"),
    ("lancamento", "Lançamento automático (API)", "service"),
    ("end", "Documento lançado", "event"),
]
TO_BE_FLOWS = [
    ("start", "extracao", ""),
    ("extracao", "validacao", ""),
    ("validacao", "gateway_div", ""),
    ("gateway_div", "conferencia", "sim (divergência)"),
    ("conferencia", "correcao", ""),
    ("correcao", "aprovacao", ""),
    ("gateway_div", "aprovacao", "não (aprovado automaticamente)"),
    ("aprovacao", "lancamento", ""),
    ("lancamento", "end", ""),
]
TO_BE_LANES = {
    "Automação (API)": ["extracao", "validacao", "lancamento"],
    "Operação (exceção)": ["conferencia", "correcao"],
    "Gestão": ["aprovacao"],
}


def _tag(ns: str, name: str) -> str:
    return f"{{{ns}}}{name}"


# --------------------------------------------------------------------------- descoberta -> modelo

def as_is_from_mining(mining: dict) -> tuple[list[tuple[str, str, str]], list[tuple[str, str, str]], dict[str, list[str]]]:
    """Constrói o AS-IS a partir do que o log mostrou (sem lista fixa de atividades)."""
    nodes: list[tuple[str, str, str]] = []
    edges: list[tuple[str, str, str]] = []
    nodes.append(("start", "Documento recebido", "event"))
    nodes.append(("end", "Documento processado", "event"))
    model_nodes: list[str] = mining["discovered_model"]["nodes"]
    model_edges: list[tuple[str, str, int]] = [
        (e["source"], e["target"], e["cases"]) for e in mining["discovered_model_edges"]
    ]
    starts = {s["activity"] for s in mining["discovered_model"]["start_activities"][:1]}
    ends = {e["activity"] for e in mining["discovered_model"]["end_activities"][:1]}

    outgoing: dict[str, int] = {}
    for source, _, _ in model_edges:
        outgoing[source] = outgoing.get(source, 0) + 1

    for activity in model_nodes:
        nodes.append((activity, activity.replace("_", " ").capitalize(), "user"))
    # gateways onde o log mostra decisão (mais de uma saída)
    gateways = {a: f"gateway_{a}" for a, count in outgoing.items() if count > 1}
    for activity, gateway_id in gateways.items():
        nodes.append((gateway_id, f"{activity.replace('_', ' ').capitalize()} — decisão", "gateway"))

    for activity in sorted(starts):
        edges.append(("start", activity, ""))
    for activity, gateway_id in sorted(gateways.items()):
        edges.append((activity, gateway_id, f"decisão observada em {activity}"))
    for source, target, cases in sorted(model_edges):
        label = f"{cases} casos"
        if source in gateways:
            edges.append((gateways[source], target, label))
        else:
            edges.append((source, target, label))
    for activity in sorted(ends):
        if activity not in gateways:
            edges.append((activity, "end", ""))

    automation = mining.get("automation_by_activity", {})
    nodes = [
        (nid, label, "service" if (nid in automation and automation[nid] >= 0.99) else kind)
        for nid, label, kind in nodes
    ]

    lanes = {"Operação": [n for n, _, k in nodes if k == "user"], "Gestão": ["aprovacao"] if "aprovacao" in model_nodes else []}
    lanes = {k: v for k, v in lanes.items() if v}
    return nodes, edges, lanes


# --------------------------------------------------------------------------- construção BPMN

def _layout(nodes: list[tuple[str, str, str]], edges: list[tuple[str, str, str]]) -> dict[str, tuple[int, int]]:
    """Layout em camadas (longest-path) para o DI — simples, determinístico e legível."""
    successors: dict[str, list[str]] = {nid: [] for nid, _, _ in nodes}
    predecessors: dict[str, int] = {nid: 0 for nid, _, _ in nodes}
    for source, target, _ in edges:
        if source in successors and target in predecessors:
            successors[source].append(target)
            predecessors[target] += 1
    layer: dict[str, int] = {nid: 0 for nid, _, _ in nodes}
    queue = [nid for nid, deg in predecessors.items() if deg == 0]
    while queue:
        current = queue.pop(0)
        for nxt in successors[current]:
            layer[nxt] = max(layer[nxt], layer[current] + 1)
            predecessors[nxt] -= 1
            if predecessors[nxt] == 0:
                queue.append(nxt)
    per_layer: dict[int, list[str]] = {}
    for nid, _, _ in nodes:
        per_layer.setdefault(layer[nid], []).append(nid)
    position: dict[str, tuple[int, int]] = {}
    for depth, ids in sorted(per_layer.items()):
        for index, nid in enumerate(ids):
            position[nid] = (160 + depth * 190, 120 + index * 120)
    return position


def build_bpmn(process_id: str, name: str, nodes: list[tuple[str, str, str]], edges: list[tuple[str, str, str]],
               lanes: dict[str, list[str]] | None = None, documentation: str = "") -> ET.ElementTree:
    definitions = ET.Element(
        _tag(BPMN_NS, "definitions"),
        {
            "xmlns:bpmn": BPMN_NS,
            "xmlns:bpmndi": BPMNDI_NS,
            "xmlns:dc": OMGDC_NS,
            "xmlns:di": OMGDI_NS,
            "xmlns:xsi": XSI_NS,
            "id": f"Definitions_{process_id}",
            "targetNamespace": "https://example.org/bpmn/process-automation-lab",
        },
    )
    process = ET.SubElement(definitions, _tag(BPMN_NS, "process"),
                            {"id": f"{process_id}_process", "name": name, "isExecutable": "false"})
    if documentation:
        ET.SubElement(process, _tag(BPMN_NS, "documentation")).text = documentation

    lanes = lanes or {}
    if lanes:
        lane_set = ET.SubElement(process, _tag(BPMN_NS, "laneSet"), {"id": f"laneSet_{process_id}"})
        for index, (lane_name, node_ids) in enumerate(lanes.items()):
            lane = ET.SubElement(lane_set, _tag(BPMN_NS, "lane"),
                                 {"id": f"lane_{process_id}_{index}", "name": lane_name})
            for nid in node_ids:
                ref = ET.SubElement(lane, _tag(BPMN_NS, "flowNodeRef"))
                ref.text = nid

    element_for = {
        "event": "startEvent" if True else "task",
        "user": "userTask",
        "service": "serviceTask",
        "gateway": "exclusiveGateway",
    }
    for nid, label, kind in nodes:
        if kind == "event" and nid == "start":
            ET.SubElement(process, _tag(BPMN_NS, "startEvent"), {"id": nid, "name": label})
        elif kind == "event":
            ET.SubElement(process, _tag(BPMN_NS, "endEvent"), {"id": nid, "name": label})
        elif kind == "gateway":
            ET.SubElement(process, _tag(BPMN_NS, "exclusiveGateway"),
                          {"id": nid, "name": label, "gatewayDirection": "Diverging"})
        else:
            element = ET.SubElement(process, _tag(BPMN_NS, element_for[kind]), {"id": nid, "name": label})
            if kind == "service":
                ET.SubElement(element, _tag(BPMN_NS, "extensionElements"))

    seen_flows: set[str] = set()
    for index, (source, target, label) in enumerate(edges, start=1):
        flow_id = f"flow_{process_id}_{index}_{source}_{target}"
        if flow_id in seen_flows:
            continue
        seen_flows.add(flow_id)
        attrs = {"id": flow_id, "sourceRef": source, "targetRef": target}
        if label:
            attrs["name"] = label
        ET.SubElement(process, _tag(BPMN_NS, "sequenceFlow"), attrs)

    _add_di(definitions, process_id, nodes, edges)
    return ET.ElementTree(definitions)


def _add_di(definitions: ET.Element, process_id: str, nodes: list[tuple[str, str, str]],
            edges: list[tuple[str, str, str]]) -> None:
    """BPMN DI: sem isso o arquivo não abre visualmente em bpmn.io/Camunda."""
    position = _layout(nodes, edges)
    diagram = ET.SubElement(definitions, _tag(BPMNDI_NS, "BPMNDiagram"), {"id": f"BPMNDiagram_{process_id}"})
    plane = ET.SubElement(diagram, _tag(BPMNDI_NS, "BPMNPlane"),
                          {"id": f"BPMNPlane_{process_id}", "bpmnElement": f"{process_id}_process"})
    for index, (nid, _, kind) in enumerate(nodes):
        x, y = position.get(nid, (200 + index * 190, 120))
        width, height = ((36, 36) if kind == "gateway" else (100, 80) if kind != "event" else (36, 36))
        shape = ET.SubElement(plane, _tag(BPMNDI_NS, "BPMNShape"),
                              {"id": f"{nid}_gui", "bpmnElement": nid})
        ET.SubElement(shape, _tag(OMGDC_NS, "Bounds"),
                      {"x": str(x), "y": str(y), "width": str(width), "height": str(height)})
    for index, (source, target, _) in enumerate(edges, start=1):
        flow_id = f"flow_{process_id}_{index}_{source}_{target}"
        start = position.get(source, (200, 120))
        end = position.get(target, (400, 120))
        edge = ET.SubElement(plane, _tag(BPMNDI_NS, "BPMNEdge"),
                             {"id": f"{flow_id}_gui", "bpmnElement": flow_id})
        ET.SubElement(edge, _tag(OMGDI_NS, "waypoint"), {"x": str(start[0] + 100), "y": str(start[1] + 40)})
        ET.SubElement(edge, _tag(OMGDI_NS, "waypoint"), {"x": str(end[0]), "y": str(end[1] + 40)})


# --------------------------------------------------------------------------- validação

def validate_bpmn(path: str) -> dict:
    """Validação estrutural: parseia, confere ids/refs, start/end e integridade do DI."""
    root = ET.parse(path).getroot()
    process = root.find(_tag(BPMN_NS, "process"))
    if process is None:
        raise ValueError("process ausente")

    ids = [el.get("id") for el in process.iter() if el.get("id")]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        raise ValueError(f"ids duplicados: {sorted(duplicates)[:5]}")

    node_tags = {"startEvent", "endEvent", "userTask", "serviceTask", "exclusiveGateway", "task"}
    nodes = {el.get("id") for el in process if el.tag.split("}")[-1] in node_tags}
    flows = [el for el in process if el.tag == _tag(BPMN_NS, "sequenceFlow")]
    dangling = [f.get("id") for f in flows if f.get("sourceRef") not in nodes or f.get("targetRef") not in nodes]
    if dangling:
        raise ValueError(f"fluxos com refs inválidas: {dangling}")

    kinds = {tag: sum(1 for el in process if el.tag.split("}")[-1] == tag) for tag in node_tags}
    if kinds["startEvent"] != 1 or kinds["endEvent"] < 1:
        raise ValueError(f"start/end inválidos: start={kinds['startEvent']} end={kinds['endEvent']}")

    disconnected = sorted(nid for nid in nodes if nid not in _connected(nodes, flows))
    if disconnected:
        raise ValueError(f"nós sem fluxo: {disconnected}")

    plane = root.find(f".//{_tag(BPMNDI_NS, 'BPMNPlane')}")
    if plane is None:
        raise ValueError("DI ausente (BPMNDiagram/BPMNPlane)")
    shapes = {el.get("bpmnElement") for el in plane if el.tag == _tag(BPMNDI_NS, "BPMNShape")}
    edges_di = {el.get("bpmnElement") for el in plane if el.tag == _tag(BPMNDI_NS, "BPMNEdge")}
    flow_ids = {f.get("id") for f in flows}
    missing_shapes = sorted(nodes - shapes)
    missing_edges = sorted(flow_ids - edges_di)
    if missing_shapes or missing_edges:
        raise ValueError(f"DI incompleto — shapes faltando: {missing_shapes}, edges faltando: {missing_edges}")

    return {
        "nodes": len(nodes),
        "sequence_flows": len(flows),
        "service_tasks": kinds["serviceTask"],
        "user_tasks": kinds.get("userTask", 0),
        "gateways": kinds.get("exclusiveGateway", 0),
        "di_shapes": len(shapes),
        "di_edges": len(edges_di),
    }


def _connected(nodes: set[str], flows: list[ET.Element]) -> set[str]:
    adjacency: dict[str, set[str]] = {n: set() for n in nodes}
    for flow in flows:
        source, target = flow.get("sourceRef"), flow.get("targetRef")
        if source in adjacency and target in adjacency:
            adjacency[source].add(target)
            adjacency[target].add(source)
    # start events não têm entrada; ainda assim contam como conectados se têm saída
    reachable: set[str] = set()
    roots = {n for n in nodes if n not in {f.get("targetRef") for f in flows}} or set(nodes)
    stack = list(roots)
    while stack:
        current = stack.pop()
        if current in reachable:
            continue
        reachable.add(current)
        stack.extend(adjacency.get(current, ()))
    return reachable


def write_models(outdir: str = "bpmn", mining_path: str = "reports/mining.json") -> dict:
    if not os.path.exists(mining_path):
        raise FileNotFoundError(f"rode `make mining` antes ({mining_path} inexistente)")
    with open(mining_path, encoding="utf-8") as fh:
        mining = json.load(fh)

    os.makedirs(outdir, exist_ok=True)
    as_is_path = os.path.join(outdir, "as_is.bpmn")
    to_be_path = os.path.join(outdir, "to_be.bpmn")

    as_nodes, as_edges, as_lanes = as_is_from_mining(mining)
    build_bpmn(
        "as_is", "Conferência documental AS-IS (descoberto do log)", as_nodes, as_edges, as_lanes,
        documentation=("Modelo descoberto por directly-follows graph sobre log sintético "
                       f"({mining['cases']} casos). Arestas anotadas com a frequência observada; "
                       "gateways marcam pontos de decisão observados no log."),
    ).write(as_is_path, encoding="utf-8", xml_declaration=True)

    build_bpmn(
        "to_be", "Conferência documental TO-BE (com automação)", TO_BE_NODES, TO_BE_FLOWS, TO_BE_LANES,
        documentation=("Modelo de destino proposto (não descoberto): extração e validação automáticas, "
                       "conferência humana apenas na exceção, aprovação sempre humana e lançamento automatizado."),
    ).write(to_be_path, encoding="utf-8", xml_declaration=True)

    result = {"as_is": validate_bpmn(as_is_path), "to_be": validate_bpmn(to_be_path)}
    print(f"bpmn: as_is {result['as_is']} | to_be {result['to_be']}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outdir", default="bpmn")
    parser.add_argument("--mining", default="reports/mining.json")
    args = parser.parse_args()
    result = write_models(args.outdir, args.mining)
    with open(args.mining, encoding="utf-8") as fh:
        mining = json.load(fh)
    print(f"gargalo medido: {mining['bottleneck_activity']} | fitness {mining['conformance']['fitness_log_to_model']:.0%} "
          f"| nós descobertos: {result['as_is']['nodes']}")


if __name__ == "__main__":
    main()
