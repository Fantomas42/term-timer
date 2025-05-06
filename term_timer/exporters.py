from datetime import datetime
from datetime import timezone

from jinja2 import Environment
from jinja2 import FileSystemLoader

from term_timer.console import console
from term_timer.constants import EXPORT_DIRECTORY
from term_timer.constants import TEMPLATES_DIRECTORY

TEMPLATES = Environment(
    loader=FileSystemLoader(TEMPLATES_DIRECTORY),
    lstrip_blocks=True,
    trim_blocks=True,
    autoescape=True,
)


class Exporter:

    def get_context(self, stats):
        return {}

    def export_html(self, stats):
        timestamp = datetime.now(
            tz=timezone.utc,  # noqa: UP017
        ).strftime('%Y%m%d_%H%M%S')

        output_path = (
            EXPORT_DIRECTORY /
            f'{ stats.cube_name }_{ timestamp }.html'
        )

        template = TEMPLATES.get_template('export.html')
        context = self.get_context(stats)

        html = template.render(**context)

        with output_path.open('w+', encoding='utf-8') as fd:
            fd.write(html)

        console.print(
            f'[success]HTML report generated at :[/success] { output_path }',
        )
