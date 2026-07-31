"""Configuration section widgets for different config categories."""
import re
from typing import Any
from typing import Final

from cubing_algs.constants import ORIENTATIONS
from cubing_algs.display.effects import EFFECTS
from cubing_algs.display.palettes import PALETTES
from cubing_algs.display.styles import STYLES
from cubing_algs.vcube import VCube
from textual.app import ComposeResult
from textual.containers import Grid
from textual.containers import Vertical
from textual.containers import VerticalScroll
from textual.widgets import Button
from textual.widgets import Checkbox
from textual.widgets import Collapsible
from textual.widgets import Input
from textual.widgets import Select
from textual.widgets import SelectionList
from textual.widgets import Static

from term_timer.config import CONFIG
from term_timer.config import SERIES_AVERAGE_KINDS
from term_timer.config import SERIES_KINDS
from term_timer.config import parse_series
from term_timer.stats import StatisticsTools

# A section value, a cube table being the only nested one
ConfigValue = str | int | float | bool | list[str] | dict[str, Any]

ConfigData = dict[str, dict[str, ConfigValue]]

# Value of a per-cube setting left to the global configuration
INHERIT: Final = 'inherit'


class ConfigSection(VerticalScroll):
    """Base class for configuration sections."""

    DEFAULT_CSS = """
    ConfigSection {
        padding: 1 2;
    }

    ConfigSection Grid {
        height: auto;
        grid-size: 2;
        grid-rows: auto;
        grid-gutter: 1 2;
        padding: 0;
    }

    ConfigSection .field-label {
        height: auto;
        padding: 0;
        text-style: bold;
    }

    /* Rows are spaced by the gutter, a margin here eating their height */
    ConfigSection .field-container {
        height: auto;
        padding: 0;
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

    def get_config_data(  # noqa: PLR6301
            self,
    ) -> ConfigData:
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
            yield Static('Sound', classes='field-label')
            with Vertical(classes='field-container'):
                yield Select(
                    options=[
                        ('Audio', 'audio'),
                        ('Terminal bell', 'terminal'),
                        ('Off', 'off'),
                    ],
                    id='sound',
                    allow_blank=False,
                    value='audio',
                )
                yield Static(
                    'Sound output mode (audio, terminal bell, or off)',
                    classes='field-help',
                )

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

            yield Static('Show Steps', classes='field-label')
            with Vertical(classes='field-container'):
                yield Checkbox(
                    'Show completed steps during the solve',
                    id='steps',
                )
                yield Static(
                    'Apply when a Bluetooth smart cube is connected',
                    classes='field-help',
                )

    def load_config(self) -> None:
        """Load timer configuration."""
        timer_config = CONFIG.get('timer', {})

        sound = self.query_one('#sound', Select)
        sound.value = timer_config.get('sound', 'audio')

        countdown = self.query_one('#countdown', Input)
        countdown.value = str(timer_config.get('countdown', 0.0))

        metronome = self.query_one('#metronome', Input)
        metronome.value = str(timer_config.get('metronome', 0.0))

        steps = self.query_one('#steps', Checkbox)
        steps.value = timer_config.get('steps', True)

    def get_config_data(
        self,
    ) -> ConfigData:
        """
        Get timer configuration data.

        Returns:
            Timer configuration dictionary with countdown, metronome and steps.

        """
        sound = self.query_one('#sound', Select)
        countdown = self.query_one('#countdown', Input)
        metronome = self.query_one('#metronome', Input)
        steps = self.query_one('#steps', Checkbox)

        return {
            'timer': {
                'sound': str(sound.value),
                'countdown': float(countdown.value or '0.0'),
                'metronome': float(metronome.value or '0.0'),
                'steps': steps.value,
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

            yield Static('Linear Display', classes='field-label')
            with Vertical(classes='field-container'):
                yield Checkbox(
                    'Use linear mode for cube display',
                    id='linear',
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

            yield Static('Style', classes='field-label')
            with Vertical(classes='field-container'):
                yield Select(
                    options=[
                        (f'{ name.title() }', name)
                        for name in STYLES
                    ],
                    id='style',
                    allow_blank=False,
                    value='default',
                )
                yield Static(
                    'Letter style for cube state display',
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

        linear = self.query_one('#linear', Checkbox)
        linear.value = cube_config.get('linear', True)

        effect = self.query_one('#effect', Select)
        effect.value = cube_config.get('effect', 'face-visible')

        style = self.query_one('#style', Select)
        style.value = cube_config.get('style', 'default')

        right_handed = self.query_one('#right-handed', Checkbox)
        right_handed.value = cube_config.get('right-handed', True)

    def get_config_data(
        self,
    ) -> ConfigData:
        """
        Get cube configuration data.

        Returns:
            Cube configuration with orientation, method, palette, and settings.

        """
        orientation = self.query_one('#orientation', Select)
        method = self.query_one('#method', Select)
        palette = self.query_one('#palette', Select)
        linear = self.query_one('#linear', Checkbox)
        effect = self.query_one('#effect', Select)
        style = self.query_one('#style', Select)
        right_handed = self.query_one('#right-handed', Checkbox)

        return {
            'cube': {
                'orientation': str(orientation.value),
                'method': str(method.value),
                'palette': str(palette.value),
                'linear': linear.value,
                'effect': str(effect.value),
                'style': str(style.value),
                'right-handed': right_handed.value,
            },
        }


DIFFICULTY_OPTIONS = [
    ('Easy', 'easy'),
    ('Normal', 'normal'),
    ('Hard', 'hard'),
]

XCROSS_SLOT_OPTIONS = [
    ('FR', 'FR'),
    ('FL', 'FL'),
    ('BR', 'BR'),
    ('BL', 'BL'),
]


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
            yield Static('FSRS', classes='field-label')
            with Vertical(classes='field-container'):
                yield Checkbox(
                    'Enable spaced repetition case selection',
                    id='fsrs',
                )
                yield Static(
                    'Use FSRS to automatically schedule case reviews',
                    classes='field-help',
                )

            yield Static('FSRS Rating', classes='field-label')
            with Vertical(classes='field-container'):
                yield Select(
                    options=[
                        ('Auto (performance-based)', 'auto'),
                        ('Manual (1-4 keys)', 'manual'),
                    ],
                    id='fsrs-rating',
                    allow_blank=False,
                    value='auto',
                )
                yield Static(
                    'Auto rates from execution data; Manual lets you'
                    ' rate with 1-4 keys (useful with Bluetooth)',
                    classes='field-help',
                )

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

            yield Static('Easy Cross Difficulty', classes='field-label')
            with Vertical(classes='field-container'):
                yield Select(
                    options=DIFFICULTY_OPTIONS,
                    id='ecross-difficulty',
                    allow_blank=False,
                    value='normal',
                )
                yield Static(
                    'Scramble difficulty for Easy Cross training',
                    classes='field-help',
                )

            yield Static('X-Cross Difficulty', classes='field-label')
            with Vertical(classes='field-container'):
                yield Select(
                    options=DIFFICULTY_OPTIONS,
                    id='xcross-difficulty',
                    allow_blank=False,
                    value='normal',
                )
                yield Static(
                    'Scramble difficulty for X-Cross training',
                    classes='field-help',
                )

            yield Static('X-Cross Slots', classes='field-label')
            with Vertical(classes='field-container'):
                yield SelectionList[str](
                    *XCROSS_SLOT_OPTIONS,
                    id='xcross-slots',
                )
                yield Static(
                    'F2L slots to aim in X-Cross scrambles',
                    classes='field-help',
                )

    def load_config(self) -> None:
        """Load trainer configuration."""
        trainer_config = CONFIG.get('trainer', {})

        step = self.query_one('#step', Select)
        step.value = trainer_config.get('step', 'oll')

        ecross_difficulty = self.query_one('#ecross-difficulty', Select)
        ecross_difficulty.value = trainer_config.get(
            'ecross-difficulty', 'normal',
        )

        xcross_difficulty = self.query_one('#xcross-difficulty', Select)
        xcross_difficulty.value = trainer_config.get(
            'xcross-difficulty', 'normal',
        )

        xcross_slots = self.query_one('#xcross-slots', SelectionList)
        for slot in trainer_config.get('xcross-slots', ['FR']):
            xcross_slots.select(slot)

        fsrs = self.query_one('#fsrs', Checkbox)
        fsrs.value = trainer_config.get('fsrs', True)

        fsrs_rating = self.query_one('#fsrs-rating', Select)
        fsrs_rating.value = trainer_config.get('fsrs-rating', 'auto')

    def get_config_data(
        self,
    ) -> ConfigData:
        """
        Get trainer configuration data.

        Returns:
            Trainer configuration with step, difficulty and slot settings.

        """
        step = self.query_one('#step', Select)
        fsrs = self.query_one('#fsrs', Checkbox)
        fsrs_rating = self.query_one('#fsrs-rating', Select)
        ecross_difficulty = self.query_one('#ecross-difficulty', Select)
        xcross_difficulty = self.query_one('#xcross-difficulty', Select)
        xcross_slots = self.query_one('#xcross-slots', SelectionList)

        return {
            'trainer': {
                'fsrs': fsrs.value,
                'fsrs-rating': str(fsrs_rating.value),
                'step': str(step.value),
                'ecross-difficulty': str(ecross_difficulty.value),
                'xcross-difficulty': str(xcross_difficulty.value),
                'xcross-slots': list(xcross_slots.selected),
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
            yield Static('Show Banner', classes='field-label')
            with Vertical(classes='field-container'):
                yield Checkbox(
                    'Display splash screen banner at startup',
                    id='banner',
                )

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

            yield Static('Show Highlights', classes='field-label')
            with Vertical(classes='field-container'):
                yield Checkbox(
                    'Display highlights after analysis',
                    id='highlights',
                )

            yield Static('Show Doctor', classes='field-label')
            with Vertical(classes='field-container'):
                yield Checkbox(
                    'Display doctor diagnostics after analysis',
                    id='doctor',
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

        banner = self.query_one('#banner', Checkbox)
        banner.value = display_config.get('banner', True)

        scramble = self.query_one('#scramble', Checkbox)
        scramble.value = display_config.get('scramble', True)

        reconstruction = self.query_one('#reconstruction', Checkbox)
        reconstruction.value = display_config.get('reconstruction', True)

        highlights = self.query_one('#highlights', Checkbox)
        highlights.value = display_config.get('highlights', True)

        doctor = self.query_one('#doctor', Checkbox)
        doctor.value = display_config.get('doctor', True)

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
    ) -> ConfigData:
        """
        Get display configuration data.

        Returns:
            Display configuration with visibility settings for various elements.

        """
        banner = self.query_one('#banner', Checkbox)
        scramble = self.query_one('#scramble', Checkbox)
        reconstruction = self.query_one('#reconstruction', Checkbox)
        highlights = self.query_one('#highlights', Checkbox)
        doctor = self.query_one('#doctor', Checkbox)
        time_graph = self.query_one('#time_graph', Checkbox)
        tps_graph = self.query_one('#tps_graph', Checkbox)
        fluency_graph = self.query_one('#fluency_graph', Checkbox)
        recognition_graph = self.query_one('#recognition_graph', Checkbox)

        return {
            'display': {
                'banner': banner.value,
                'scramble': scramble.value,
                'reconstruction': reconstruction.value,
                'highlights': highlights.value,
                'doctor': doctor.value,
                'time_graph': time_graph.value,
                'tps_graph': tps_graph.value,
                'fluency_graph': fluency_graph.value,
                'recognition_graph': recognition_graph.value,
            },
        }


class CubeCard(Vertical):
    """Editable card holding one Bluetooth cube of the configuration."""

    DEFAULT_CSS = """
    CubeCard {
        height: auto;
    }

    CubeCard Collapsible {
        border: round $primary;
        padding: 0 1;
        margin-bottom: 1;
    }

    CubeCard Contents {
        padding: 0 0 0 1;
    }

    CubeCard Grid {
        height: auto;
        grid-size: 2;
        grid-rows: auto;
        grid-gutter: 1 2;
    }

    CubeCard .cube-remove {
        margin-top: 1;
        width: auto;
    }
    """

    def __init__(self, index: int, label: str, data: dict[str, Any]) -> None:
        """
        Initialize the card of one cube.

        The card edits the raw configuration table rather than a loaded
        CubeDevice, the only way to tell a setting left inherited from
        one explicitly set to the value it would have inherited.

        Args:
            index: Rank of the card, making its identifier unique.
            label: Label naming the cube, empty for a cube being added.
            data: Configuration table of the cube.

        """
        super().__init__(id=f'cube-{ index }', classes='cube-card')
        self.label_name = label
        self.data = data

    def compose(self) -> ComposeResult:
        """
        Compose the fields of one cube.

        Yields:
            Textual widgets editing the cube.

        """
        gyroscope = self.data.get('use_gyroscope')
        threshold = self.data.get('rotation_threshold')

        # A cube being added is the one worth editing, so it opens alone
        with Collapsible(
            title=self.card_title,
            collapsed=bool(self.label_name),
        ):
            with Grid():
                yield Static('Short Name', classes='field-label')
                with Vertical(classes='field-container'):
                    yield Input(
                        value=self.label_name,
                        placeholder='gan12',
                        classes='cube-label',
                    )
                    yield Static(
                        'Name selecting the cube: term-timer solve -b gan12',
                        classes='field-help',
                    )

                yield Static('Display Name', classes='field-label')
                with Vertical(classes='field-container'):
                    yield Input(
                        value=str(self.data.get('name', '')),
                        placeholder='GAN 356 i3',
                        classes='cube-name',
                    )
                    yield Static(
                        'Name shown for this cube, yours to '
                        'choose (optional)',
                        classes='field-help',
                    )

                yield Static('Device Address', classes='field-label')
                with Vertical(classes='field-container'):
                    yield Input(
                        value=str(self.data.get('address', '')),
                        placeholder='00:00:00:00:00:00',
                        classes='cube-address',
                    )
                    yield Static(
                        'MAC address, or system UUID on macOS. '
                        'Empty to find the cube by scanning',
                        classes='field-help',
                    )

                yield Static('Gyroscope', classes='field-label')
                with Vertical(classes='field-container'):
                    yield Select(
                        options=[
                            ('Inherit', INHERIT),
                            ('Enabled', 'true'),
                            ('Disabled', 'false'),
                        ],
                        value=(
                            INHERIT if gyroscope is None
                            else str(bool(gyroscope)).lower()
                        ),
                        allow_blank=False,
                        classes='cube-gyroscope',
                    )
                    yield Static(
                        'Inherit follows the default gyroscope above',
                        classes='field-help',
                    )

                yield Static('Rotation Threshold', classes='field-label')
                with Vertical(classes='field-container'):
                    yield Input(
                        value='' if threshold is None else str(threshold),
                        type='number',
                        placeholder='inherited',
                        classes='cube-threshold',
                    )
                    yield Static(
                        'Detection threshold of this cube, '
                        'empty to inherit the default above',
                        classes='field-help',
                    )

            yield Button(
                'Remove this cube',
                variant='error',
                classes='cube-remove',
            )

    def field_value(self, field: str, composing: str = '') -> str:
        """
        Read a field of the card, its configured value while composing.

        Args:
            field: Class naming the input holding the field.
            composing: Value to read while the input is not composed yet.

        Returns:
            The value being edited, stripped.

        """
        inputs = self.query(f'.cube-{ field }').results(Input)

        return next(
            (entry.value.strip() for entry in inputs),
            composing,
        )

    @property
    def card_title(self) -> str:
        """Get the line naming the folded cube, its fields once typed."""
        label = self.field_value('label', self.label_name).lower()

        if not label:
            return 'New cube'

        parts = (
            label,
            self.field_value('name', str(self.data.get('name', ''))),
            self.field_value('address', str(self.data.get('address', ''))),
        )

        return ' - '.join(part for part in parts if part)

    @property
    def label_value(self) -> str:
        """Get the label naming the cube, empty while it has none."""
        return self.field_value('label', self.label_name).lower()

    def as_config(self) -> dict[str, Any]:
        """
        Build the configuration table of the edited cube.

        Returns:
            The cube table, holding only the settings it overrides.

        """
        gyroscope = self.query_one('.cube-gyroscope', Select)
        threshold = self.query_one('.cube-threshold', Input).value.strip()

        # A field left empty is an absent key, never an empty value
        cube: dict[str, Any] = {
            field: value
            for field in ('name', 'address')
            if (value := self.field_value(field))
        }

        if gyroscope.value != INHERIT:
            cube['use_gyroscope'] = gyroscope.value == 'true'

        if threshold:
            cube['rotation_threshold'] = float(threshold)

        return cube

    def on_input_changed(self, event: Input.Changed) -> None:
        """Keep the folded title showing the fields being typed."""
        titling = {'cube-label', 'cube-name', 'cube-address'}

        if event.input.classes & titling:
            self.query_one(Collapsible).title = self.card_title


class BluetoothSection(ConfigSection):
    """Configuration section for Bluetooth settings."""

    section_name = 'bluetooth'

    DEFAULT_CSS = """
    /* The cube list stands outside the grid, so it spaces itself */
    BluetoothSection > .field-label {
        margin-top: 1;
    }

    BluetoothSection .cube-list {
        height: auto;
    }

    BluetoothSection .cube-add {
        margin-top: 1;
        width: auto;
    }
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
        """Initialize the Bluetooth section."""
        super().__init__(*args, **kwargs)
        self.default_card: CubeCard | None = None

    @staticmethod
    def compose() -> ComposeResult:
        """
        Compose the Bluetooth section.

        Yields:
            Textual widgets for the Bluetooth configuration section.

        """
        with Grid():
            yield Static('Default Cube', classes='field-label')
            with Vertical(classes='field-container'):
                yield Select[str](options=[], id='default')
                yield Static(
                    'Cube connected when none is asked for. '
                    'Blank scans for one of the cubes below',
                    classes='field-help',
                )

            yield Static('Default Gyroscope', classes='field-label')
            with Vertical(classes='field-container'):
                yield Checkbox(
                    'Enable gyroscope-based rotation detection',
                    id='use_gyroscope',
                )
                yield Static(
                    'Applied to every cube leaving it inherited',
                    classes='field-help',
                )

            yield Static('Default Threshold', classes='field-label')
            with Vertical(classes='field-container'):
                yield Input(
                    id='rotation_threshold',
                    type='number',
                    placeholder='75.0',
                )
                yield Static(
                    'Gyroscope rotation detection threshold (degrees), '
                    'applied to every cube leaving it inherited',
                    classes='field-help',
                )

        yield Static('Cubes', classes='field-label')
        yield Vertical(classes='cube-list', id='cubes')
        yield Button('Add a cube', variant='primary', classes='cube-add')

    @property
    def cards(self) -> list[CubeCard]:
        """Get the cube cards currently edited."""
        return list(self.query(CubeCard))

    def load_config(self) -> None:
        """Load Bluetooth configuration."""
        bluetooth_config = CONFIG.get('bluetooth', {})

        use_gyroscope = self.query_one('#use_gyroscope', Checkbox)
        use_gyroscope.value = bluetooth_config.get('use_gyroscope', True)

        rotation_threshold = self.query_one('#rotation_threshold', Input)
        rotation_threshold.value = str(
            bluetooth_config.get('rotation_threshold', 75.0),
        )

        cubes = self.query_one('#cubes', Vertical)
        cubes.remove_children()

        configured: dict[str, Any] = bluetooth_config.get('cubes', {})

        for index, (label, data) in enumerate(configured.items()):
            cubes.mount(CubeCard(index, str(label), data))

        # Cards answer with their configured label until they compose
        self.refresh_defaults(
            str(bluetooth_config.get('default', '')),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Add or remove a cube when a card button is pressed."""
        cubes = self.query_one('#cubes', Vertical)

        if event.button.has_class('cube-add'):
            cubes.mount(CubeCard(len(self.cards), '', {}))
        elif event.button.has_class('cube-remove'):
            for node in event.button.ancestors_with_self:
                if isinstance(node, CubeCard):
                    node.remove()
                    break
        else:
            return

        event.stop()
        self.refresh_defaults()

        if not self.is_loading:
            app = self.app
            if hasattr(app, 'mark_modified'):
                app.mark_modified()

    def refresh_defaults(self, chosen: str = '') -> None:
        """
        Offer the edited cubes as the default one, keeping the choice.

        The choice follows the card rather than the label it carries, so
        that renaming the designated cube keeps designating it.

        Args:
            chosen: Label to select, the current card when empty.

        """
        default = self.query_one('#default', Select)
        cards = self.cards

        if chosen:
            self.default_card = next(
                (card for card in cards if card.label_value == chosen),
                None,
            )

        labels = [card.label_value for card in cards if card.label_value]
        default.set_options((label, label) for label in labels)

        selected = next(
            (card.label_value for card in cards if card is self.default_card),
            '',
        )

        if selected in labels:
            default.value = selected

    def on_select_changed(self, event: Select.Changed) -> None:
        """Remember which card the default cube is picked from."""
        super().on_select_changed(event)

        if event.select.id != 'default' or event.value is Select.BLANK:
            return

        self.default_card = next(
            (
                card for card in self.cards
                if card.label_value == str(event.value)
            ),
            None,
        )

    def on_input_changed(self, event: Input.Changed) -> None:
        """Keep the default cube in sync with the labels being typed."""
        super().on_input_changed(event)

        if event.input.has_class('cube-label'):
            self.refresh_defaults()

    def get_config_data(
        self,
    ) -> ConfigData:
        """
        Get Bluetooth configuration data.

        Returns:
            Bluetooth configuration with the cubes and gyroscope settings.

        """
        use_gyroscope = self.query_one('#use_gyroscope', Checkbox)
        rotation_threshold = self.query_one('#rotation_threshold', Input)
        default = self.query_one('#default', Select)

        cubes: dict[str, Any] = {
            card.label_value: card.as_config()
            for card in self.cards
            if card.label_value
        }

        chosen = '' if default.is_blank() else str(default.value)

        return {
            'bluetooth': {
                'default': chosen if chosen in cubes else '',
                'use_gyroscope': use_gyroscope.value,
                'rotation_threshold': float(
                    rotation_threshold.value or '75.0',
                ),
                'cubes': cubes,
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
            yield Static('Trim', classes='field-label')
            with Vertical(classes='field-container'):
                yield Input(
                    id='trim',
                    placeholder='p5',
                )
                yield Static(
                    'Trim for averages: pN percent (WCA = p5), '
                    'm median, or N fixed count per side',
                    classes='field-help',
                )

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

            yield Static('Solve Metrics', classes='field-label')
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
                    id='solve_metrics',
                )
                yield Static(
                    'Move count metrics to track on solves',
                    classes='field-help',
                )

            yield Static('Ao Projections', classes='field-label')
            with Vertical(classes='field-container'):
                yield SelectionList[int](
                    ('Ao5', 5),
                    ('Ao12', 12),
                    ('Ao100', 100),
                    ('Ao1000', 1000),
                    id='ao_projections',
                )
                yield Static(
                    'Show next-solve BPA/WPA range and PB target '
                    'for these averages when solving',
                    classes='field-help',
                )

            yield Static('Live Series', classes='field-label')
            with Vertical(classes='field-container'):
                yield Input(
                    id='live_series',
                    placeholder='mo3 ao5 ao12',
                )
                yield Static(
                    'Averages shown inline after each solve, in the '
                    'order entered: ao/mo + solve count (ao5 = last 5)',
                    classes='field-help',
                )

            yield Static('Session Series', classes='field-label')
            with Vertical(classes='field-container'):
                yield Input(
                    id='session_series',
                    placeholder='mo3 ao5 ao12 ao100 ao1000',
                )
                yield Static(
                    'Session table averages and tracked records, in the '
                    'order entered: ao/mo + solve count (ao5 = last 5)',
                    classes='field-help',
                )

            yield Static('Graph Series', classes='field-label')
            with Vertical(classes='field-container'):
                yield Input(
                    id='graph_series',
                    placeholder='ao5 ao12 ao100 ao1000',
                )
                yield Static(
                    'Trend graph curves, in the order entered: '
                    'ao/mo/mb/mw + solve count (ao5 = average of last 5)',
                    classes='field-help',
                )

    def load_config(self) -> None:
        """Load statistics configuration."""
        stats_config = CONFIG.get('statistics', {})

        trim = self.query_one('#trim', Input)
        trim.value = str(stats_config.get('trim', 'p5'))

        distribution = self.query_one('#distribution', Input)
        distribution.value = str(stats_config.get('distribution', 0))

        metrics = self.query_one('#solve_metrics', SelectionList)
        metrics_list = stats_config.get('solve_metrics', ['htm', 'qtm', 'stm'])
        for m in metrics_list:
            metrics.select(m)

        projections = self.query_one('#ao_projections', SelectionList)
        for limit in stats_config.get('ao_projections', []):
            projections.select(limit)

        live_series = self.query_one('#live_series', Input)
        live_series.value = ' '.join(
            str(token)
            for token in stats_config.get(
                'live_series', ['mo3', 'ao5', 'ao12'],
            )
        )

        session_series = self.query_one('#session_series', Input)
        session_series.value = ' '.join(
            str(token)
            for token in stats_config.get(
                'session_series', ['mo3', 'ao5', 'ao12', 'ao100', 'ao1000'],
            )
        )

        graph_series = self.query_one('#graph_series', Input)
        graph_series.value = ' '.join(
            str(token)
            for token in stats_config.get(
                'graph_series', ['ao5', 'ao12', 'ao100', 'ao1000'],
            )
        )

    def get_config_data(
        self,
    ) -> ConfigData:
        """
        Get statistics configuration data.

        Returns:
            Statistics configuration with distribution and metrics settings.

        """
        trim = self.query_one('#trim', Input)
        distribution = self.query_one('#distribution', Input)
        metrics = self.query_one('#solve_metrics', SelectionList)
        projections = self.query_one('#ao_projections', SelectionList)
        live_series = self.query_one('#live_series', Input)
        session_series = self.query_one('#session_series', Input)
        graph_series = self.query_one('#graph_series', Input)

        metrics_list = metrics.selected

        live_series_list = self.normalize_series(
            live_series.value, SERIES_AVERAGE_KINDS,
        )
        session_series_list = self.normalize_series(
            session_series.value, SERIES_AVERAGE_KINDS,
        )
        graph_series_list = self.normalize_series(graph_series.value)

        return {
            'statistics': {
                'trim': StatisticsTools.normalize_trim(trim.value),
                'distribution': int(distribution.value or '0'),
                'solve_metrics': metrics_list,
                'ao_projections': sorted(projections.selected),
                'live_series': live_series_list,
                'session_series': session_series_list,
                'graph_series': graph_series_list,
            },
        }

    @staticmethod
    def normalize_series(
            value: str,
            kinds: tuple[str, ...] = SERIES_KINDS,
    ) -> list[str]:
        """
        Normalise a free-text series field into a list of tokens.

        Splits on whitespace or commas, then runs the tokens through
        ``parse_series`` to drop duplicates and invalid entries while
        keeping the order entered.

        Args:
            value: Raw text typed in the series input.
            kinds: Kinds to accept; defaults to every supported kind.

        Returns:
            Ordered list of normalised ``kindsize`` tokens.

        """
        raw_tokens = re.split(r'[\s,]+', value.strip())
        return [
            f'{ kind }{ size }'
            for kind, size in parse_series(raw_tokens, kinds)
        ]


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
    ) -> ConfigData:
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
