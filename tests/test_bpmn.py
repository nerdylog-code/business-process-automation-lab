import os
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.bpmn import BPMN_NS, build_bpmn, validate_bpmn, write_models  # noqa: E402


class TestBpmn(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.paths = write_models(cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_models_written_and_valid(self):
        for name in ("as_is.bpmn", "to_be.bpmn"):
            path = os.path.join(self.tmp.name, name)
            self.assertTrue(os.path.exists(path))
            info = validate_bpmn(path)
            self.assertGreaterEqual(info["sequence_flows"], 5)
            self.assertGreaterEqual(info["nodes"], 7)

    def test_to_be_has_service_tasks(self):
        info = validate_bpmn(os.path.join(self.tmp.name, "to_be.bpmn"))
        self.assertGreaterEqual(info["service_tasks"], 3, "TO-BE precisa das tarefas automatizadas")
        self.assertGreaterEqual(info["user_tasks"], 1, "aprovação humana continua no TO-BE")

    def test_as_is_has_no_service_tasks(self):
        info = validate_bpmn(os.path.join(self.tmp.name, "as_is.bpmn"))
        self.assertEqual(info["service_tasks"], 0)

    def test_validation_rejects_dangling_flow(self):
        tree = build_bpmn("x", "X", [("start", "a"), ("end", "b")], {})
        root = tree.getroot()
        process = root.find(f"{{{BPMN_NS}}}process")
        bad = ET.SubElement(process, f"{{{BPMN_NS}}}sequenceFlow")
        bad.set("id", "flow_bad")
        bad.set("sourceRef", "start")
        bad.set("targetRef", "nao_existe")
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "bad.bpmn")
            tree.write(path, encoding="utf-8", xml_declaration=True)
            with self.assertRaises(ValueError):
                validate_bpmn(path)

    def test_lanes_reference_existing_nodes(self):
        tree = ET.parse(os.path.join(self.tmp.name, "to_be.bpmn"))
        process = tree.getroot().find(f"{{{BPMN_NS}}}process")
        node_ids = {el.get("id") for el in process if el.tag.endswith(("Task", "Event", "Gateway"))}
        refs = [el.text for el in process.iter(f"{{{BPMN_NS}}}flowNodeRef")]
        self.assertTrue(refs)
        for ref in refs:
            self.assertIn(ref, node_ids)


if __name__ == "__main__":
    unittest.main()
