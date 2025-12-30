"""Configuration section widgets for different config categories."""
from typing import Any

from cubing_algs.constants import ORIENTATIONS
from cubing_algs.effects import EFFECTS
from cubing_algs.palettes import PALETTES
from cubing_algs.vcube import VCube
from textual.app import ComposeResult
from textual.containers import Grid
from textual.containers import Vertical
from textual.containers import VerticalScroll
from textual.widgets import Checkbox
from textual.widgets import Input
from textual.widgets import Select
from textual.widgets import SelectionList
from textual.widgets import Static

from term_timer.config import CONFIG


class ConfigSection(VerticalScroll):
    """Base class for configuration sections."""

    DEFAULT_CSS = """
    ConfigSection {
        padding: 1 2;
    }

    ConfigSection Grid {
        grid-size: 2;
        grid-gutter: 0 2;
        padding: 0;
    }

    ConfigSection .field-label {
        height: auto;
        padding: 0;
        text-style: bold;
        margin-top: 1;
    }

    ConfigSection .field-container {
        height: auto;
        padding: 0;
        margin-top: 1;
    }

    ConfigSection .field-help {
        height: auto;
        color: $text-muted;
        text-style: italic;
        padding: 0;
        margin-top: 0;
    }

    ConfigSection Input {
        width: 100%;
        margin-bottom: 0;
    }

    ConfigSection Select {
        width: 100%;
        margin-bottom: 0;
    }

    ConfigSection Checkbox {
        height: auto;
        padding: 0;
    }

    ConfigSection SelectionList {
        height: auto;
        max-height: 15;
        border: solid $primary;
    }
    """

    section_name: str = ''

    def __init__(self, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
        """Initialize the configuration section."""
        super().__init__(*args, **kwargs)
        self.is_loading = True

    def on_mount(self) -> None:
        """Load configuration when mounted."""
        self.set_timer(0.1, self.load_initial_config)

    def load_initial_config(self) -> None:
        """Load initial configuration without triggering change events."""
        self.load_config()
        self.set_timer(0.05, self.finish_loading)

    def finish_loading(self) -> None:
        """Finish loading after all pending events are processed."""
        self.is_loading = False

    def load_config(self) -> None:
        """Load configuration from file. Override in subclasses."""

    def get_config_data(  # noqa : PLR6301
            self,
    ) -> dict[str, dict[str, str | int | float | bool | list[str]]]:
        """
        Get configuration data from widgets. Override in subclasses.

        Returns:
            Configuration data dictionary with section keys and config values.

        """
        return {}

    def on_input_changed(self, _event: Input.Changed) -> None:
        """Mark app as modified when input changes."""
        if self.is_loading:
            return
        app = self.app
        if hasattr(app, 'mark_modified'):
            app.mark_modified()

    def on_checkbox_changed(self, _event: Checkbox.Changed) -> None:
        """Mark app as modified when checkbox changes."""
        if self.is_loading:
            return
        app = self.app
        if hasattr(app, 'mark_modified'):
            app.mark_modified()

    def on_select_changed(self, _event: Select.Changed) -> None:
        """Mark app as modified when select changes."""
        if self.is_loading:
            return
        app = self.app
        if hasattr(app, 'mark_modified'):
            app.mark_modified()

    def on_selection_list_selected_changed(
        self,
        _event: SelectionList.SelectedChanged[str],
    ) -> None:
        """Mark app as modified when selection list changes."""
        if self.is_loading:
            return
        app = self.app
        if hasattr(app, 'mark_modified'):
            app.mark_modified()


class TimerSection(ConfigSection):
    """Configuration section for timer settings."""

    section_name = 'timer'

    @staticmethod
    def compose() -> ComposeResult:
        """
        Compose the timer section.

        Yields:
            Textual widgets for the timer configuration section.

        """
        with Grid():
            yield Static('Countdown', classes='field-label')
            with Vertical(classes='field-container'):
                yield Input(
                    id='countdown',
                    type='number',
                    placeholder='0.0',
                )
                yield Static(
                    'Inspection countdown time in seconds (0 to disable)',
                    classes='field-help',
                )

            yield Static('Metronome', classes='field-label')
            with Vertical(classes='field-container'):
                yield Input(
                    id='metronome',
                    type='number',
                    placeholder='0.0',
                )
                yield Static(
                    'Metronome beep interval in seconds (0 to disable)',
                    classes='field-help',
                )

    def load_config(self) -> None:
        """Load timer configuration."""
        timer_config = CONFIG.get('timer', {})

        countdown = self.query_one('#countdown', Input)
        countdown.value = str(timer_config.get('countdown', 0.0))

        metronome = self.query_one('#metronome', Input)
        metronome.value = str(timer_config.get('metronome', 0.0))

    def get_config_data(
        self,
    ) -> dict[str, dict[str, str | int | float | bool | list[str]]]:
        """
        Get timer configuration data.

        Returns:
            Timer configuration dictionary with countdown and metronome values.

        """
        countdown = self.query_one('#countdown', Input)
        metronome = self.query_one('#metronome', Input)

        return {
            'timer': {
                'countdown': float(countdown.value or '0.0'),
                'metronome': float(metronome.value or '0.0'),
            },
        }


class CubeSection(ConfigSection):
    """Configuration section for cube settings."""

    section_name = 'cube'

    @staticmethod
    def compose() -> ComposeResult:
        """
        Compose the cube section.

        Yields:
            Textual widgets for the cube configuration section.

        """
        cube = VCube()
        orientations = []

        for faces in ORIENTATIONS:
            moves = cube.compute_orientation_moves(faces)
            if moves:
                orientations.append(
                    (
                        f'{ faces }: ({ moves })',
                        faces,
                    ),
                )
            else:
                orientations.append((faces, faces))

        with Grid():
            yield Static('Orientation', classes='field-label')
            with Vertical(classes='field-container'):
                yield Select(
                    options=orientations,
                    id='orientation',
                    allow_blank=False,
                    value='UF',
                )
                yield Static(
                    'Default cube orientation (top face + front face)',
                    classes='field-help',
                )

            yield Static('Method', classes='field-label')
            with Vertical(classes='field-container'):
                yield Select(
                    options=[
                        ('Layer by Layer', 'lbl'),
                        ('CFOP', 'cfop'),
                        ('CFOP with 4-step F2L', 'cf4op'),
                        ('Raw moves', 'raw'),
                    ],
                    id='method',
                    allow_blank=False,
                    value='cf4op',
                )
                yield Static(
                    'Analysis method for solve reconstruction',
                    classes='field-help',
                )

            yield Static('Palette', classes='field-label')
            with Vertical(classes='field-container'):
                yield Select(
                    options=[
                        (f'{ name.title() }', name)
                        for name in PALETTES
                    ],
                    id='palette',
                    allow_blank=False,
                    value='default',
                )
                yield Static(
                    'Color palette for cube display',
                    classes='field-help',
                )

            yield Static('Effect', classes='field-label')
            with Vertical(classes='field-container'):
                yield Select(
                    options=[
                        (f'{ name.title() }', name)
                        for name in EFFECTS
                    ],
                    id='effect',
                    allow_blank=False,
                    value='face-visible',
                )
                yield Static(
                    'Visual effect for cube state display',
                    classes='field-help',
                )

            yield Static('Right-handed', classes='field-label')
            with Vertical(classes='field-container'):
                yield Checkbox(
                    'Optimize for right-handed solving',
                    id='right-handed',
                )

    def load_config(self) -> None:
        """Load cube configuration."""
        cube_config = CONFIG.get('cube', {})

        orientation = self.query_one('#orientation', Select)
        orientation.value = cube_config.get('orientation', 'DF')

        method = self.query_one('#method', Select)
        method.value = cube_config.get('method', 'cf4op')

        palette = self.query_one('#palette', Select)
        palette.value = cube_config.get('palette', 'default')

        effect = self.query_one('#effect', Select)
        effect.value = cube_config.get('effect', 'face-visible')

        right_handed = self.query_one('#right-handed', Checkbox)
        right_handed.value = cube_config.get('right-handed', True)

    def get_config_data(
        self,
    ) -> dict[str, dict[str, str | int | float | bool | list[str]]]:
        """
        Get cube configuration data.

        Returns:
            Cube configuration with orientation, method, palette, and settings.

        """
        orientation = self.query_one('#orientation', Select)
        method = self.query_one('#method', Select)
        palette = self.query_one('#palette', Select)
        effect = self.query_one('#effect', Select)
        right_handed = self.query_one('#right-handed', Checkbox)

        return {
            'cube': {
                'orientation': str(orientation.value),
                'method': str(method.value),
                'palette': str(palette.value),
                'effect': str(effect.value),
                'right-handed': right_handed.value,
            },
        }


class TrainerSection(ConfigSection):
    """Configuration section for trainer settings."""

    section_name = 'trainer'

    @staticmethod
    def compose() -> ComposeResult:
        """
        Compose the trainer section.

        Yields:
            Textual widgets for the trainer configuration section.

        """
        with Grid():
            yield Static('Step', classes='field-label')
            with Vertical(classes='field-container'):
                yield Select(
                    options=[
                        ('Cross', 'cross'),
                        ('Easy Cross', 'ecross'),
                        ('F2L', 'f2l'),
                        ('Advanced F2L', 'af2l'),
                        ('OLL', 'oll'),
                        ('PLL', 'pll'),
                    ],
                    id='step',
                    allow_blank=False,
                    value='oll',
                )
                yield Static(
                    'Default training step for trainer mode',
                    classes='field-help',
                )

    def load_config(self) -> None:
        """Load trainer configuration."""
        trainer_config = CONFIG.get('trainer', {})

        step = self.query_one('#step', Select)
        step.value = trainer_config.get('step', 'oll')

    def get_config_data(
        self,
    ) -> dict[str, dict[str, str | int | float | bool | list[str]]]:
        """
        Get trainer configuration data.

        Returns:
            Trainer configuration dictionary with training step setting.

        """
        step = self.query_one('#step', Select)

        return {
            'trainer': {
                'step': str(step.value),
            },
        }


class DisplaySection(ConfigSection):
    """Configuration section for display settings."""

    section_name = 'display'

    @staticmethod
    def compose() -> ComposeResult:
        """
        Compose the display section.

        Yields:
            Textual widgets for the display configuration section.

        """
        with Grid():
            yield Static('Show Scramble', classes='field-label')
            with Vertical(classes='field-container'):
                yield Checkbox(
                    'Display cube in scrambled state',
                    id='scramble',
                )

            yield Static('Show Reconstruction', classes='field-label')
            with Vertical(classes='field-container'):
                yield Checkbox(
                    'Show solve reconstruction analysis',
                    id='reconstruction',
                )

            yield Static('Show Advices', classes='field-label')
            with Vertical(classes='field-container'):
                yield Checkbox(
                    'Display advices after analyse',
                    id='advices',
                )

            yield Static('Show Time Graph', classes='field-label')
            with Vertical(classes='field-container'):
                yield Checkbox(
                    'Display time scatter graph',
                    id='time_graph',
                )

            yield Static('Show TPS Graph', classes='field-label')
            with Vertical(classes='field-container'):
                yield Checkbox(
                    'Display turns per second graph',
                    id='tps_graph',
                )

            yield Static('Show Fluency Graph', classes='field-label')
            with Vertical(classes='field-container'):
                yield Checkbox(
                    'Display fluency graph',
                    id='fluency_graph',
                )

            yield Static('Show Recognition Graph', classes='field-label')
            with Vertical(classes='field-container'):
                yield Checkbox(
                    'Display case recognition time graph',
                    id='recognition_graph',
                )

    def load_config(self) -> None:
        """Load display configuration."""
        display_config = CONFIG.get('display', {})

        scramble = self.query_one('#scramble', Checkbox)
        scramble.value = display_config.get('scramble', True)

        reconstruction = self.query_one('#reconstruction', Checkbox)
        reconstruction.value = display_config.get('reconstruction', True)

        advices = self.query_one('#advices', Checkbox)
        advices.value = display_config.get('advices', True)

        time_graph = self.query_one('#time_graph', Checkbox)
        time_graph.value = display_config.get('time_graph', True)

        tps_graph = self.query_one('#tps_graph', Checkbox)
        tps_graph.value = display_config.get('tps_graph', True)

        fluency_graph = self.query_one('#fluency_graph', Checkbox)
        fluency_graph.value = display_config.get('fluency_graph', True)

        recognition_graph = self.query_one('#recognition_graph', Checkbox)
        recognition_graph.value = display_config.get('recognition_graph', True)

    def get_config_data(
        self,
    ) -> dict[str, dict[str, str | int | float | bool | list[str]]]:
        """
        Get display configuration data.

        Returns:
            Display configuration with visibility settings for various elements.

        """
        scramble = self.query_one('#scramble', Checkbox)
        reconstruction = self.query_one('#reconstruction', Checkbox)
        advices = self.query_one('#advices', Checkbox)
        time_graph = self.query_one('#time_graph', Checkbox)
        tps_graph = self.query_one('#tps_graph', Checkbox)
        fluency_graph = self.query_one('#fluency_graph', Checkbox)
        recognition_graph = self.query_one('#recognition_graph', Checkbox)

        return {
            'display': {
                'scramble': scramble.value,
                'reconstruction': reconstruction.value,
                'advices': advices.value,
                'time_graph': time_graph.value,
                'tps_graph': tps_graph.value,
                'fluency_graph': fluency_graph.value,
                'recognition_graph': recognition_graph.value,
            },
        }


class BluetoothSection(ConfigSection):
    """Configuration section for Bluetooth settings."""

    section_name = 'bluetooth'

    @staticmethod
    def compose() -> ComposeResult:
        """
        Compose the Bluetooth section.

        Yields:
            Textual widgets for the Bluetooth configuration section.

        """
        with Grid():
            yield Static('Device Address', classes='field-label')
            with Vertical(classes='field-container'):
                yield Input(
                    id='address',
                    placeholder='00:00:00:00:00:00',
                )
                yield Static(
                    'Bluetooth MAC address of smart cube (empty for auto)',
                    classes='field-help',
                )

            yield Static('Use Gyroscope', classes='field-label')
            with Vertical(classes='field-container'):
                yield Checkbox(
                    'Enable gyroscope-based rotation detection',
                    id='use_gyroscope',
                )

            yield Static('Rotation Threshold', classes='field-label')
            with Vertical(classes='field-container'):
                yield Input(
                    id='rotation_threshold',
                    type='number',
                    placeholder='75.0',
                )
                yield Static(
                    'Gyroscope rotation detection threshold (degrees)',
                    classes='field-help',
                )

    def load_config(self) -> None:
        """Load Bluetooth configuration."""
        bluetooth_config = CONFIG.get('bluetooth', {})

        address = self.query_one('#address', Input)
        address.value = bluetooth_config.get('address', '')

        use_gyroscope = self.query_one('#use_gyroscope', Checkbox)
        use_gyroscope.value = bluetooth_config.get('use_gyroscope', True)

        rotation_threshold = self.query_one('#rotation_threshold', Input)
        rotation_threshold.value = str(
            bluetooth_config.get('rotation_threshold', 75.0),
        )

    def get_config_data(
        self,
    ) -> dict[str, dict[str, str | int | float | bool | list[str]]]:
        """
        Get Bluetooth configuration data.

        Returns:
            Bluetooth configuration with device address and gyroscope settings.

        """
        address = self.query_one('#address', Input)
        use_gyroscope = self.query_one('#use_gyroscope', Checkbox)
        rotation_threshold = self.query_one('#rotation_threshold', Input)

        return {
            'bluetooth': {
                'address': address.value,
                'use_gyroscope': use_gyroscope.value,
                'rotation_threshold': float(
                    rotation_threshold.value or '75.0',
                ),
            },
        }


class StatisticsSection(ConfigSection):
    """Configuration section for statistics settings."""

    section_name = 'statistics'

    @staticmethod
    def compose() -> ComposeResult:
        """
        Compose the statistics section.

        Yields:
            Textual widgets for the statistics configuration section.

        """
        with Grid():
            yield Static('Distribution', classes='field-label')
            with Vertical(classes='field-container'):
                yield Input(
                    id='distribution',
                    type='integer',
                    placeholder='0',
                )
                yield Static(
                    'Distribution calculation method (0 for default)',
                    classes='field-help',
                )

            yield Static('Metrics', classes='field-label')
            with Vertical(classes='field-container'):
                yield SelectionList[str](
                    ('HTM', 'htm'),
                    ('QTM', 'qtm'),
                    ('STM', 'stm'),
                    ('ETM', 'etm'),
                    ('RTM', 'rtm'),
                    ('QSTM', 'qstm'),
                    ('OBTM', 'obtm'),
                    ('OBQTM', 'obqtm'),
                    ('RBTM', 'rbtm'),
                    ('BTM', 'btm'),
                    ('BQTM', 'bqtm'),
                    id='metrics',
                )
                yield Static(
                    'Move count metrics to track',
                    classes='field-help',
                )

    def load_config(self) -> None:
        """Load statistics configuration."""
        stats_config = CONFIG.get('statistics', {})

        distribution = self.query_one('#distribution', Input)
        distribution.value = str(stats_config.get('distribution', 0))

        metrics = self.query_one('#metrics', SelectionList)
        metrics_list = stats_config.get('metrics', ['htm', 'qtm', 'stm'])
        for m in metrics_list:
            metrics.select(m)

    def get_config_data(
        self,
    ) -> dict[str, dict[str, str | int | float | bool | list[str]]]:
        """
        Get statistics configuration data.

        Returns:
            Statistics configuration with distribution and metrics settings.

        """
        distribution = self.query_one('#distribution', Input)
        metrics = self.query_one('#metrics', SelectionList)

        metrics_list = metrics.selected

        return {
            'statistics': {
                'distribution': int(distribution.value or '0'),
                'metrics': metrics_list,
            },
        }


class ServerSection(ConfigSection):
    """Configuration section for server settings."""

    section_name = 'server'

    @staticmethod
    def compose() -> ComposeResult:
        """
        Compose the server section.

        Yields:
            Textual widgets for the server configuration section.

        """
        with Grid():
            yield Static('Domain', classes='field-label')
            with Vertical(classes='field-container'):
                yield Input(
                    id='domain',
                    placeholder='localhost',
                )
                yield Static(
                    'Server hostname for web interface',
                    classes='field-help',
                )

            yield Static('Port', classes='field-label')
            with Vertical(classes='field-container'):
                yield Input(
                    id='port',
                    type='integer',
                    placeholder='8333',
                )
                yield Static(
                    'Server port number (1024-65535)',
                    classes='field-help',
                )

    def load_config(self) -> None:
        """Load server configuration."""
        server_config = CONFIG.get('server', {})

        domain = self.query_one('#domain', Input)
        domain.value = server_config.get('domain', 'localhost')

        port = self.query_one('#port', Input)
        port.value = str(server_config.get('port', 8333))

    def get_config_data(
        self,
    ) -> dict[str, dict[str, str | int | float | bool | list[str]]]:
        """
        Get server configuration data.

        Returns:
            Server configuration with domain and port settings.

        """
        domain = self.query_one('#domain', Input)
        port = self.query_one('#port', Input)

        port_value = int(port.value or '8333')
        if port_value < 1024 or port_value > 65535:
            port_value = 8333

        return {
            'server': {
                'domain': domain.value or 'localhost',
                'port': port_value,
            },
        }
