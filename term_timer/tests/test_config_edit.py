"""Tests for the Bluetooth section of the configuration editor."""
import unittest
from contextlib import AsyncExitStack
from typing import Any
from typing import ClassVar
from unittest.mock import patch

from textual.widgets import Button
from textual.widgets import Input
from textual.widgets import TabbedContent

from term_timer.config_edit.app import ConfigEditApp
from term_timer.config_edit.sections import BluetoothSection

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
            {'name': '', 'address': '99:88:77:66:55:44'},
        )

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
