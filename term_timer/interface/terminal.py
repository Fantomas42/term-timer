class Terminal:

    @staticmethod
    def clear_line(full) -> None:
        if full:
            print(f'\r{ " " * 100}\r', flush=True, end='')
        else:
            print('\r', end='')

    @staticmethod
    def back(size) -> None:
        print('\b' * size, end='')

    @staticmethod
    def beep() -> None:
        print('\a', end='', flush=True)
