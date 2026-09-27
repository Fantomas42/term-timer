"""
Command line of the V2 design system.

    python -m term_timer.server.design          # regenerate theme.css
    python -m term_timer.server.design check    # theme.css is up to date
    python -m term_timer.server.design lint     # stylesheets and templates
"""
import argparse
import sys
from pathlib import Path

from term_timer.server.design import THEME_FILE
from term_timer.server.design import THEME_STYLESHEET
from term_timer.server.design import DesignTheme
from term_timer.server.design.lint import DesignLint


def report(lines: list[str]) -> None:
    """Write lines on the standard error."""
    for line in lines:
        sys.stderr.write(f'{ line }\n')


def contrast_failures(theme: DesignTheme) -> list[str]:
    """
    Describe the contrast pairs under their level.

    Returns:
        One message per failing pair.

    """
    return [
        f'contrast { check.text } on { check.background }:'
        f' { check.ratio:.2f} < { check.minimum } ({ check.level })'
        for check in theme.contrast_checks()
        if not check.passed
    ]


def generate(source: Path, target: Path) -> int:
    """
    Write the theme stylesheet, unless a contrast pair fails.

    Returns:
        The process exit code.

    """
    theme = DesignTheme.load(source)
    failures = contrast_failures(theme)
    if failures:
        report(failures)
        return 1
    target.write_text(theme.stylesheet(), encoding='utf-8')
    return 0


def check(source: Path, target: Path) -> int:
    """
    Verify the committed stylesheet matches the theme source.

    Returns:
        The process exit code.

    """
    theme = DesignTheme.load(source)
    failures = contrast_failures(theme)
    current = target.read_text(encoding='utf-8') if target.exists() else ''
    if current != theme.stylesheet():
        failures.append(f'{ target } is stale, regenerate it')
    report(failures)
    return 1 if failures else 0


def lint() -> int:
    """
    Lint the V2 stylesheets and templates.

    Returns:
        The process exit code.

    """
    violations = DesignLint().run()
    report([str(violation) for violation in violations])
    return 1 if violations else 0


def main(argv: list[str] | None = None) -> int:
    """
    Parse the command line and run the command.

    Returns:
        The process exit code.

    """
    parser = argparse.ArgumentParser(prog='python -m term_timer.server.design')
    parser.add_argument(
        'command', nargs='?', default='generate',
        choices=('generate', 'check', 'lint'),
    )
    arguments = parser.parse_args(argv)

    if arguments.command == 'lint':
        return lint()
    if arguments.command == 'check':
        return check(THEME_FILE, THEME_STYLESHEET)
    return generate(THEME_FILE, THEME_STYLESHEET)


if __name__ == '__main__':
    sys.exit(main())
