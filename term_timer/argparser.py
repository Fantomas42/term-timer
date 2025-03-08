import argparse


class ArgumentParser(argparse.ArgumentParser):

    class _ArgumentGroup(argparse._ArgumentGroup):  # noqa: SLF001
        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, **kwargs)
            self.title = self.title and self.title.title()

    class _HelpFormatter(argparse.RawTextHelpFormatter):
        def _format_usage(self, *args, **kwargs) -> str:
            return super()._format_usage(*args, **kwargs).replace(
                'usage:', 'Usage:', 1,
            )

        def _format_action_invocation(self, action: argparse.Action) -> str:
            action.help = action.help and (
                action.help[0].upper() + action.help[1:]
            )
            if action.help and not action.help.endswith('.'):
                action.help = f'{ action.help }.'
            return super()._format_action_invocation(action)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs, formatter_class=self._HelpFormatter)

    def add_argument_group(self, *args, **kwargs) -> _ArgumentGroup:
        group = self._ArgumentGroup(self, *args, **kwargs)
        self._action_groups.append(group)
        return group
