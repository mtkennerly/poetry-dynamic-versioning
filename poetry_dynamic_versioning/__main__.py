import sys

from poetry_dynamic_versioning import (
    _state,
    cli,
)


def main() -> None:
    try:
        _state.cli_mode = True
        args = cli.parse_args()

        if args.cmd is None:
            cli.apply(standalone=True)
        elif args.cmd == cli.Command.enable:
            cli.enable()
    except Exception as e:
        print("Error: {}".format(e), file=sys.stderr)
        sys.exit(1)
