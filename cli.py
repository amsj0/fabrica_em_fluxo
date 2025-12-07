import argparse
import json
from pathlib import Path
from fluxo.schema import demo
from fluxo.export import export_package, import_scenario
from fluxo.service import execute
from fluxo.storage import Store


def main():
    parser = argparse.ArgumentParser(description='Fábrica em Fluxo · planejamento agregado educativo')
    parser.add_argument('--scenario', type=Path)
    parser.add_argument('--export', type=Path, default=Path('runtime/demo.zip'))
    parser.add_argument('--home', type=Path)
    args = parser.parse_args()
    scenario = import_scenario(args.scenario.read_bytes()) if args.scenario else demo()
    store = Store(args.home)
    try:
        bundle = execute(store, store.save(scenario))
        args.export.parent.mkdir(parents=True, exist_ok=True)
        args.export.write_bytes(export_package(bundle))
        print(json.dumps({'run_id': bundle['run_id'], 'months': len(bundle['result']['rows']),
                          'export': str(args.export.resolve()), 'hash': bundle['hashes']['result']}, indent=2))
    finally:
        store.close()


if __name__ == '__main__':
    main()
