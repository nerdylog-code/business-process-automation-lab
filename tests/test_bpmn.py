import os
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.bpmn import (  # noqa: E402
    BPMN_NS,
    BPMNDI_NS,
    TO_BE_FLOWS,
    TO_BE_NODES,
    as_is_from_mining,
    build_bpmn,
    validate_bpmn,
    write_models,
)
from src.generate_event_log import generate  # noqa: E402
from src.mining import analyze  # noqa: E402


class TestBpmn(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        events, _ = generate(cases=90, seed=42)
        cls.report = analyze(events)
        cls.result = write_models(cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_models_written_and_valid(self):
        for name, info in self.result.items():
            path = os.path.join(self.tmp.name, f"{name}.bpmn")
            self.assertTrue(os.path.exists(path))
            self.assertGreaterEqual(info["sequence_flows"], 5)
            self.assertGreaterEqual(info["nodes"], 7)
            self.assertEqual(info["di_shapes"], info["nodes"], "todo nó precisa de shape no DI")
            self.assertEqual(info["di_edges"], info["sequence_flows"], "todo fluxo precisa de edge no DI")

    def test_xml_is_wellformed_and_namespaced(self):
        path = os.path.join(self.tmp.name, "as_is.bpmn")
        root = ET.parse(path).getroot()
        self.assertEqual(root.tag, f"{{{BPMN_NS}}}definitions")
        process = root.find(f"{{{BPMN_NS}}}process")
        self.assertIsNotNone(process)
        self.assertIsNotNone(root.find(f".//{{{BPMNDI_NS}}}BPMNDiagram"))

    def test_as_is_is_derived_from_the_log(self):
        """AS-IS tem de reflejar exatamente as atividades descobertas — não uma lista fixa."""
        nodes, edges, _ = as_is_from_mining(self.report)
        task_ids = {nid for nid, _, kind in nodes if kind in ("user", "service")}
        discovered = set(self.report["discovered_model"]["nodes"])
        self.assertEqual(task_ids, discovered)
        discovered_pairs = {(e["source"], e["target"]) for e in self.report["discovered_model_edges"]}
        # quando o log ramifica, a aresta passa por um gateway: o gateway é transparente para o teste
        gateway_of = {nid: nid[len("gateway_"):] for nid, _, kind in nodes if kind == "gateway"}
        observed_pairs = set()
        for source, target, _ in edges:
            source = gateway_of.get(source, source)
            if target in gateway_of:  # aresta de entrada do gateway
                continue
            if source in discovered and target in discovered:
                observed_pairs.add((source, target))
        self.assertEqual(observed_pairs, discovered_pairs)

    def test_as_is_changes_when_log_changes(self):
        """Se alguém hardcodar o AS-IS, este teste quebra."""
        events, _ = generate(cases=80, seed=9, rework_rate=0.0)
        other = analyze(events)
        nodes, _, _ = as_is_from_mining(other)
        task_ids = {nid for nid, _, kind in nodes if kind in ("user", "service")}
        self.assertNotIn("correcao", task_ids)

    def test_gateway_appears_only_where_log_branches(self):
        nodes, _, _ = as_is_from_mining(self.report)
        gateways = [nid for nid, _, kind in nodes if kind == "gateway"]
        self.assertTrue(gateways, "o log tem ramificação (correcao) => precisa de gateway")
        self.assertEqual(len(gateways), 1)

    def test_to_be_has_automation_and_keeps_human_approval(self):
        info = self.result["to_be"]
        self.assertGreaterEqual(info["service_tasks"], 3, "TO-BE precisa das tarefas automatizadas")
        self.assertGreaterEqual(info["user_tasks"], 1, "aprovação humana continua no TO-BE")
        self.assertEqual(info["gateways"], 1)

    def test_every_flow_endpoint_is_a_declared_node(self):
        for name in ("as_is", "to_be"):
            root = ET.parse(os.path.join(self.tmp.name, f"{name}.bpmn")).getroot()
            process = root.find(f"{{{BPMN_NS}}}process")
            node_ids = {el.get("id") for el in process if el.tag.split("}")[-1] in
                        {"startEvent", "endEvent", "userTask", "serviceTask", "exclusiveGateway", "task"}}
            for flow in process.findall(f"{{{BPMN_NS}}}sequenceFlow"):
                self.assertIn(flow.get("sourceRef"), node_ids)
                self.assertIn(flow.get("targetRef"), node_ids)

    def test_every_node_reachable_from_start(self):
        for name in ("as_is", "to_be"):
            root = ET.parse(os.path.join(self.tmp.name, f"{name}.bpmn")).getroot()
            process = root.find(f"{{{BPMN_NS}}}process")
            nodes = {el.get("id") for el in process if el.tag.split("}")[-1] in
                     {"startEvent", "endEvent", "userTask", "serviceTask", "exclusiveGateway"}}
            adjacency = {}
            for flow in process.findall(f"{{{BPMN_NS}}}sequenceFlow"):
                adjacency.setdefault(flow.get("sourceRef"), set()).add(flow.get("targetRef"))
            seen, stack = set(), ["start"]
            while stack:
                current = stack.pop()
                if current in seen:
                    continue
                seen.add(current)
                stack.extend(adjacency.get(current, ()))
            self.assertEqual(seen, nodes, f"{name}: nós inalcançáveis a partir do start")

    def test_build_bpmn_rejects_invalid_model(self):
        with self.assertRaises(Exception):
            tree = build_bpmn("bad", "modelo inválido",
                              [("start", "i", "event"), ("end", "f", "event")],
                              [("start", "inexistente", "")])
            path = os.path.join(self.tmp.name, "bad.bpmn")
            tree.write(path, encoding="utf-8")
            validate_bpmn(path)

    def test_missing_mining_file_is_reported_clearly(self):
        with self.assertRaises(FileNotFoundError):
            write_models(self.tmp.name, mining_path=os.path.join(self.tmp.name, "nao_existe.json"))

    def test_custom_to_be_model_builds(self):
        tree = build_bpmn("custom", "custom", list(TO_BE_NODES), list(TO_BE_FLOWS))
        path = os.path.join(self.tmp.name, "custom.bpmn")
        tree.write(path, encoding="utf-8")
        self.assertEqual(validate_bpmn(path)["service_tasks"], 3)


if __name__ == "__main__":
    unittest.main()
