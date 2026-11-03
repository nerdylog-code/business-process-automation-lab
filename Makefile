PY ?= python3

.PHONY: all data mining bpmn impact report test openapi check-openapi repro api clean

all: data mining bpmn impact report

data:
	$(PY) -m src.generate_event_log

mining:
	$(PY) -m src.mining

bpmn:
	$(PY) -m src.bpmn

impact:
	$(PY) -m src.impact

report:
	$(PY) -m src.report

test:
	$(PY) -m unittest discover -s tests -v

repro:
	$(PY) scripts/check_reproducibility.py

openapi:
	$(PY) scripts/export_openapi.py

check-openapi:
	$(PY) scripts/check_openapi.py

api:
	$(PY) -m uvicorn src.automation_service:app --reload --port 8080

clean:
	rm -rf reports dashboard/*.html data/*.csv bpmn/*.bpmn __pycache__ **/__pycache__
