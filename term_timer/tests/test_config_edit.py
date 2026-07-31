"""Tests for the Bluetooth section of the configuration editor."""
import tempfile
import unittest
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any
from typing import ClassVar
from unittest.mock import patch

import rtoml
from textual.containers import Vertical
from textual.widgets import Button
from textual.widgets import Collapsible
from textual.widgets import Input
from textual.widgets import TabbedContent

from term_timer.config_edit.app import ConfigEditApp
from term_timer.config_edit.sections import BluetoothSection
from term_timer.config_edit.toolbar import ConfigToolbar

MULTI_CUBE_CONFIG: dict[str, Any] = {
    'bluetooth': {
        'default': 'weilong',
        'use_gyroscope': True,
        'rotation_threshold': 75.0,
        'cubes': {
            'gan12': {
                'name': 'GAN 12 ui FreePlay',
                'address': 'AA:BB:CC:DD:EE:FF',
            },
            'weilong': {
                'name': 'MoYu WeiLong v10 AI',
                'address': '11:22:33:44:55:77',
                'use_gyroscope': False,
                'rotation_threshold': 60.0,
            },
        },
    },
}


class BluetoothSectionTestCase(unittest.IsolatedAsyncioTestCase):
    """Base driving the editor on a given configuration."""

    config: ClassVar[dict[str, Any]] = MULTI_CUBE_CONFIG

    async def asyncSetUp(self) -> None:
        """Open the editor on the Bluetooth tab."""
        patcher = patch(
            'term_timer.config_edit.sections.CONFIG',
            self.config,
        )
        patcher.start()
        self.addCleanup(patcher.stop)

        self.app = ConfigEditApp()

        stack = AsyncExitStack()
        self.pilot = await stack.enter_async_context(self.app.run_test())
        self.addAsyncCleanup(stack.aclose)

        await self.pilot.pause(0.4)
        self.app.query_one(TabbedContent).active = 'bluetooth-tab'
        await self.pilot.pause(0.3)

        self.section = self.app.query_one(BluetoothSection)

    @property
    def saved(self) -> dict[str, Any]:
        """Get the Bluetooth table the editor would write."""
        return dict(self.section.get_config_data()['bluetooth'])


class TestBluetoothSectionCubes(BluetoothSectionTestCase):
    """Tests for editing the list of cubes."""

    async def test_every_cube_is_loaded(self) -> None:
        """Each configured cube gets its own card."""
        self.assertEqual(
            [card.label_value for card in self.section.cards],
            ['gan12', 'weilong'],
        )

    async def test_saving_round_trips_the_cubes(self) -> None:
        """Saving without touching anything gives the configuration back."""
        self.assertEqual(
            self.saved['cubes'],
            MULTI_CUBE_CONFIG['bluetooth']['cubes'],
        )

    async def test_inherited_settings_stay_out_of_the_file(self) -> None:
        """A cube overriding nothing writes no override."""
        self.assertNotIn('use_gyroscope', self.saved['cubes']['gan12'])
        self.assertNotIn('rotation_threshold', self.saved['cubes']['gan12'])

    async def test_default_cube_is_kept(self) -> None:
        """The designated cube survives a load and a save."""
        self.assertEqual(self.saved['default'], 'weilong')

    async def test_adding_a_cube(self) -> None:
        """A cube added and named is written out."""
        self.section.query_one('.cube-add', Button).press()
        await self.pilot.pause(0.3)

        card = self.section.cards[-1]
        card.query_one('.cube-label', Input).value = 'newcube'
        card.query_one('.cube-address', Input).value = '99:88:77:66:55:44'
        await self.pilot.pause(0.3)

        self.assertEqual(
            self.saved['cubes']['newcube'],
            {'address': '99:88:77:66:55:44'},
        )

    async def test_empty_fields_write_no_key(self) -> None:
        """A field left empty stays out of the file, never an empty value."""
        card = self.section.cards[0]
        card.query_one('.cube-address', Input).value = ''
        await self.pilot.pause(0.3)

        self.assertEqual(
            self.saved['cubes']['gan12'],
            {'name': 'GAN 12 ui FreePlay'},
        )

    async def test_renaming_the_default_cube_keeps_it(self) -> None:
        """The designated cube stays designated once relabelled."""
        card = self.section.cards[1]
        card.query_one('.cube-label', Input).value = 'moyu'
        await self.pilot.pause(0.3)

        self.assertEqual(self.saved['default'], 'moyu')

    async def test_renaming_another_cube_keeps_the_default(self) -> None:
        """Relabelling a cube leaves the designated one alone."""
        card = self.section.cards[0]
        card.query_one('.cube-label', Input).value = 'gan'
        await self.pilot.pause(0.3)

        self.assertEqual(self.saved['default'], 'weilong')

    async def test_an_unnamed_cube_is_dropped(self) -> None:
        """A cube left without a label reaches nothing, so it is dropped."""
        self.section.query_one('.cube-add', Button).press()
        await self.pilot.pause(0.3)

        self.assertEqual(list(self.saved['cubes']), ['gan12', 'weilong'])

    async def test_removing_a_cube(self) -> None:
        """A removed cube leaves the configuration."""
        self.section.cards[0].query_one('.cube-remove', Button).press()
        await self.pilot.pause(0.3)

        self.assertEqual(list(self.saved['cubes']), ['weilong'])

    async def test_removing_the_default_cube_clears_it(self) -> None:
        """Removing the designated cube leaves the choice to the scan."""
        self.section.cards[1].query_one('.cube-remove', Button).press()
        await self.pilot.pause(0.3)

        self.assertEqual(self.saved['default'], '')


class TestBluetoothSectionFolding(BluetoothSectionTestCase):
    """Tests for the cards folding the cubes they edit."""

    @property
    def titles(self) -> list[str]:
        """Get the line each card shows while folded."""
        return [
            card.query_one(Collapsible).title
            for card in self.section.cards
        ]

    async def test_configured_cubes_are_folded(self) -> None:
        """An already configured cube opens folded."""
        self.assertEqual(
            [
                card.query_one(Collapsible).collapsed
                for card in self.section.cards
            ],
            [True, True],
        )

    async def test_folded_card_names_its_cube(self) -> None:
        """A folded card tells which cube it holds."""
        self.assertEqual(
            self.titles,
            [
                'gan12 - GAN 12 ui FreePlay - AA:BB:CC:DD:EE:FF',
                'weilong - MoYu WeiLong v10 AI - 11:22:33:44:55:77',
            ],
        )

    async def test_folded_cubes_share_the_screen(self) -> None:
        """Every cube stays visible at once, none pushed off screen."""
        heights = [card.region.height for card in self.section.cards]

        self.assertLess(sum(heights), self.section.container_size.height)

    async def test_expanded_fields_are_not_clipped(self) -> None:
        """A row is as tall as its widgets, help lines included."""
        card = self.section.cards[0]
        card.query_one(Collapsible).collapsed = False
        await self.pilot.pause(0.3)

        for container in card.query('.field-container').results(Vertical):
            self.assertGreaterEqual(
                container.region.height,
                sum(child.region.height for child in container.children),
            )

    async def test_added_cube_opens_alone(self) -> None:
        """The cube being added is the one worth showing expanded."""
        self.section.query_one('.cube-add', Button).press()
        await self.pilot.pause(0.3)

        self.assertEqual(
            [
                card.query_one(Collapsible).collapsed
                for card in self.section.cards
            ],
            [True, True, False],
        )
        self.assertEqual(self.titles[-1], 'New cube')

    async def test_title_follows_the_fields(self) -> None:
        """Naming a cube names its card right away."""
        self.section.query_one('.cube-add', Button).press()
        await self.pilot.pause(0.3)

        card = self.section.cards[-1]
        card.query_one('.cube-label', Input).value = 'aichuan'
        card.query_one('.cube-name', Input).value = 'MoYu AI'
        await self.pilot.pause(0.3)

        self.assertEqual(self.titles[-1], 'aichuan - MoYu AI')


class TestWriteConfigFile(unittest.TestCase):
    """Tests for writing the edited configuration back to the file."""

    def setUp(self) -> None:
        """Point the toolbar at a throwaway configuration file."""
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)

        self.config_file = Path(directory.name) / 'config.toml'

        patcher = patch(
            'term_timer.config_edit.toolbar.CONFIG_FILE',
            self.config_file,
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def write(self, content: str) -> None:
        """Install a configuration file to be edited."""
        self.config_file.write_text(content, encoding='utf-8')

    @property
    def written(self) -> dict[str, Any]:
        """Get the configuration as it stands on disk."""
        return rtoml.load(self.config_file)

    def test_sections_are_written(self) -> None:
        """The edited sections land in the file."""
        ConfigToolbar.write_config_file({'timer': {'sound': 'audio'}})

        self.assertEqual(self.written['timer']['sound'], 'audio')

    def test_missing_file_is_created(self) -> None:
        """Saving without a configuration file writes a new one."""
        ConfigToolbar.write_config_file({'timer': {'countdown': 3.0}})

        self.assertEqual(self.written, {'timer': {'countdown': 3.0}})

    def test_unknown_sections_survive(self) -> None:
        """A section the editor ignores, like the theme, is kept."""
        self.write(
            '[ui]\n'
            'timer_base = "bold #FF0000"\n',
        )

        ConfigToolbar.write_config_file({'timer': {'sound': 'audio'}})

        self.assertEqual(self.written['ui']['timer_base'], 'bold #FF0000')

    def test_unknown_keys_survive(self) -> None:
        """A key the editor ignores inside an edited section is kept."""
        self.write(
            '[timer]\n'
            'sound = "beep"\n'
            'experimental = true\n',
        )

        ConfigToolbar.write_config_file({'timer': {'sound': 'audio'}})

        self.assertEqual(
            self.written['timer'],
            {'sound': 'audio', 'experimental': True},
        )

    def test_removed_cube_is_forgotten(self) -> None:
        """A table the editor owns is replaced, not merged."""
        self.write(
            '[bluetooth]\n'
            'default = ""\n'
            '\n'
            '[bluetooth.cubes.gan12]\n'
            'name = "GAN 12 ui FreePlay"\n'
            '\n'
            '[bluetooth.cubes.weilong]\n'
            'name = "MoYu WeiLong v10 AI"\n',
        )

        ConfigToolbar.write_config_file(
            {
                'bluetooth': {
                    'default': '',
                    'cubes': {'gan12': {'name': 'GAN 12 ui FreePlay'}},
                },
            },
        )

        self.assertEqual(list(self.written['bluetooth']['cubes']), ['gan12'])
