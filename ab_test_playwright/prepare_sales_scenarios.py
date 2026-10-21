from qa_orm import main
from terminal_setup import SetupCancelled


if __name__ == '__main__':
    try:
        main('scenarios')
    except (SetupCancelled, KeyboardInterrupt, EOFError):
        print('Setup cancelled; no fixture changes applied')
        raise SystemExit(130) from None
    except ValueError as error:
        print(str(error))
        raise SystemExit(2) from None
