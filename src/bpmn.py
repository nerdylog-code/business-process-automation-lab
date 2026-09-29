"""Gera e valida modelos BPMN 2.0 (AS-IS descoberto do log e TO-BE com automação).

Sem dependências externas: o XML é construído e validado com xml.etree.
Uso: python -m src.bpmn [--mining reports/mining.json] [--outdir bpmn]
"""
from __future__ import annotations

import argparse
import json
import os
import xml.etree.ElementTree as ET

BPMN_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"
BPMNDI_NS = "http://www.omg.org/spec/BPMN/20100524/DI"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"

AS_IS = [
    ("start", "Recebimento do documento"),
    ("triagem", "Triagem manual"),
    ("conferencia", "Conferência manual"),
    ("gateway", "Divergência?"),
    ("correcao", "Correção"),
    ("aprovacao", "Aprovação"),
    ("lancamento", "Lançamento"),
    ("end", "Documento lançado"),
]

TO_BE = [
    ("start", "Recebimento do documento"),
    ("extracao", "Extração automática (API)"),
    ("validacao", "Validação por regras (automática)"),
    ("gateway", "Divergência?"),
    ("conferencia", "Conferência humana (exceção)"),
    ("correcao", "Correção"),
    ("aprovacao", "Aprovação humana"),
    ("lancamento", "Lançamento automático (API)"),
    ("end", "Documento lançado"),
]

AUTOMATED_IDS = {"extracao", "validacao", "lancamento"}


def _tag(ns: str, name: str) -> str:
    return f"{{{ns}}}{name}"


def build_bpmn(process_id: str, name: str, nodes: list[tuple[str, str]], lanes: dict[str, list[str]],
               automated_ids: set[str] | None = None) -> ET.ElementTree:
    automated = AUTOMATED_IDS if automated_ids is None else automated_ids
    definitions = ET.Element(
        _tag(BPMN_NS, "definitions"),
        {
            "xmlns:bpmn": BPMN_NS,
            "xmlns:bpmndi": BPMNDI_NS,
            "xmlns:xsi": XSI_NS,
            "id": f"Definitions_{process_id}",
            "targetNamespace": "https://example.org/bpmn/process-automation-lab",
        },
    )
    process = ET.SubElement(definitions, _tag(BPMN_NS, "process"), {"id": f"{process_id}_process", "name": name, "isExecutable": "false"})
    ET.SubElement(process, _tag(BPMN_NS, "documentation")).text = (
        "Modelo sintético gerado pelo Business Process Automation Lab. "
        "AS-IS descoberto de log de eventos; TO-BE com automação - simulação, sem operação real."
    )

    lane_set = ET.SubElement(process, _tag(BPMN_NS, "laneSet"), {"id": f"laneSet_{process_id}"})
    for lane_name, node_ids in lanes.items():
        lane = ET.SubElement(lane_set, _tag(BPMN_NS, "lane"), {"id": f"lane_{process_id}_{node_ids[0]}", "name": lane_name})
        for nid in node_ids:
            ref = ET.SubElement(lane, _tag(BPMN_NS, "flowNodeRef"))
            ref.text = nid

    for nid, label in nodes:
        if nid == "start":
            el = ET.SubElement(process, _tag(BPMN_NS, "startEvent"), {"id": nid, "name": label})
        elif nid == "end":
            el = ET.SubElement(process, _tag(BPMN_NS, "endEvent"), {"id": nid, "name": label})
        elif nid == "gateway":
            el = ET.SubElement(
                process,
                _tag(BPMN_NS, "exclusiveGateway"),
                {"id": nid, "name": label, "gatewayDirection": "Diverging"},
            )
        else:
            kind = "serviceTask" if nid in automated else "userTask"
            el = ET.SubElement(process, _tag(BPMN_NS, kind), {"id": nid, "name": label})
            if kind == "serviceTask":
                ET.SubElement(
                    el,
                    _tag(BPMN_NS, "extensionElements"),
                )
        del el

    flows = _flows(process_id, nodes)
    for fid, src, dst, label in flows:
        attrs = {"id": fid, "sourceRef": src, "targetRef": dst}
        if label:
            attrs["name"] = label
        ET.SubElement(process, _tag(BPMN_NS, "sequenceFlow"), attrs)

    return ET.ElementTree(definitions)


def _flows(process_id: str, nodes: list[tuple[str, str]]):
    order = [n[0] for n in nodes]
    flows = []
    for i in range(len(order) - 1):
        src, dst = order[i], order[i + 1]
        label = ""
        if src == "gateway" and dst == "correcao":
            label = "sim (divergência)"
        flows.append((f"flow_{i+1}_{src}_{dst}", src, dst, label))
    if "gateway" in order and "aprovacao" in order:
        flows.append(("flow_sem_divergencia", "gateway", "aprovacao", "não"))
    return flows


def validate_bpmn(path: str) -> dict:
    """Validação estrutural: parseia, confere ids únicos, refs de fluxo e existência de start/end."""
    tree = ET.parse(path)
    root = tree.getroot()
    process = root.find(_tag(BPMN_NS, "process"))
    if process is None:
        raise ValueError("process ausente")
    ids = [el.get("id") for el in process]
    if len(ids) != len(set(ids)):
        raise ValueError("ids duplicados no processo")
    nodes = {
        el.get("id")
        for el in process
        if el.tag
        in {
            _tag(BPMN_NS, "startEvent"),
            _tag(BPMN_NS, "endEvent"),
            _tag(BPMN_NS, "userTask"),
            _tag(BPMN_NS, "serviceTask"),
            _tag(BPMN_NS, "exclusiveGateway"),
        }
    }
    flows = [el for el in process if el.tag == _tag(BPMN_NS, "sequenceFlow")]
    dangling = [f.get("id") for f in flows if f.get("sourceRef") not in nodes or f.get("targetRef") not in nodes]
    if dangling:
        raise ValueError(f"fluxos com refs inválidas: {dangling}")
    kinds = {n: sum(1 for el in process if el.tag == _tag(BPMN_NS, n)) for n in ("startEvent", "endEvent")}
    if kinds["startEvent"] != 1 or kinds["endEvent"] < 1:
        raise ValueError(f"start/end inválidos: {kinds}")
    return {
        "nodes": len(nodes),
        "sequence_flows": len(flows),
        "service_tasks": sum(1 for el in process if el.tag == _tag(BPMN_NS, "serviceTask")),
        "user_tasks": sum(1 for el in process if el.tag == _tag(BPMN_NS, "userTask")),
    }


def write_models(outdir: str = "bpmn") -> dict:
    os.makedirs(outdir, exist_ok=True)
    lanes_as_is = {"Operação": ["triagem", "conferencia", "correcao"], "Gestão": ["aprovacao", "lancamento"]}
    lanes_to_be = {
        "Automação (API)": ["extracao", "validacao", "lancamento"],
        "Operação (exceção)": ["conferencia", "correcao"],
        "Gestão": ["aprovacao"],
    }
    as_is_path = os.path.join(outdir, "as_is.bpmn")
    to_be_path = os.path.join(outdir, "to_be.bpmn")
    build_bpmn("as_is", "Conferência documental AS-IS", AS_IS, lanes_as_is, automated_ids=set()).write(as_is_path, encoding="utf-8", xml_declaration=True)
    build_bpmn("to_be", "Conferência documental TO-BE (com automação)", TO_BE, lanes_to_be, automated_ids=AUTOMATED_IDS).write(to_be_path, encoding="utf-8", xml_declaration=True)
    result = {"as_is": validate_bpmn(as_is_path), "to_be": validate_bpmn(to_be_path)}
    print(f"bpmn: as_is {result['as_is']} | to_be {result['to_be']}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outdir", default="bpmn")
    parser.add_argument("--mining", default="reports/mining.json", help="usado apenas para citar o gargalo no log")
    args = parser.parse_args()
    result = write_models(args.outdir)
    if os.path.exists(args.mining):
        with open(args.mining, encoding="utf-8") as fh:
            mining = json.load(fh)
        print(f"gargalo medido no AS-IS: {mining.get('bottleneck_activity')} (entra como 'conferência humana' no TO-BE)")


if __name__ == "__main__":
    main()
