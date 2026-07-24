"""Signal Hub pipeline entry point. Run via `python main.py`."""
from pipeline.build import run

if __name__ == '__main__':
    document = run()
    print(f"Run status: {document['meta']['run_status']}")
    print(f"Symbols in document: {len(document['symbols'])}")
