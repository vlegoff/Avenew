# -*- coding: utf-8 -*-

"""
Characters

Characters are (by default) Objects setup to be puppeted by Accounts.
They are what you "see" in game. The Character class in this module
is setup to be the "default" character type created by the default
creation commands.

"""

from evennia.utils.utils import lazy_property
from evennia.contrib.ingame_python.typeclasses import EventCharacter
from evennia.contrib.ingame_python.utils import register_events, time_event, phrase_event

from auto.behaviors.behaviorhandler import BehaviorHandler
from logic.character.equipment import EquipmentHandler
from logic.character.events import *
from logic.character.stats import StatsHandler
from logic.geo import get_direction
from typeclasses.shared import AvenewObject
from world.log import login as log

# Constants
MAP = r"""
Crossroad

   Map                        Roads

        N                     {fn}
  NW    {fl}    NE
    {ell}   {fl}   {erl}                 {ern}
     {ell}  {fl}  {erl}                  {eln}
      {ell} {fl} {erl}
       {ell}{fl}{erl}                    {rn}
W{ll}{ll}{ll}{ll}{ll}{ll}{ll}*{rl}{rl}{rl}{rl}{rl}{rl}{rl}E             {ln}
       {hll}{bl}{hrl}
      {hll} {bl} {hrl}                   {hrn}
     {hll}  {bl}  {hrl}                  {hln}
    {hll}   {bl}   {hrl}
  SW    {bl}    SE
        S                     {bn}
"""


@register_events
class Character(AvenewObject, EventCharacter):
    """
    The character, representing an account-character (connected) or
    NPC (non-connected).
    """

    _events = {
        "can_delete": (["character"], CAN_DELETE),
        "can_move": (["character", "origin", "destination"], CAN_MOVE),
        "can_part": (["character", "departing"], CAN_PART),
        "can_say": (["speaker", "character", "message"], CAN_SAY, phrase_event),
        "delete": (["character"], DELETE),
        "greet": (["character", "newcomer"], GREET),
        "move": (["character", "origin", "destination"], MOVE),
        "pre_turn": (["character", "vehicle", "crossroad"], PRE_TURN),
        "post_turn": (["character", "vehicle", "crossroad"], POST_TURN),
        "puppeted": (["character"], PUPPETED),
        "say": (["speaker", "character", "message"], SAY, phrase_event),
        "time": (["character"], TIME, None, time_event),
        "unpuppeted": (["character"], UNPUPPETED),
    }

    repr = "representations.character.CharacterRepr"

    @lazy_property
    def behaviors(self):
        """Return the behavior handler for this character."""
        return BehaviorHandler(self)

    @lazy_property
    def equipment(self):
        """Return the equipment handler for this character."""
        return EquipmentHandler(self)

    @lazy_property
    def stats(self):
        """Return the stat handler for this character."""
        return StatsHandler(self)

    def at_post_puppet(self):
        """
        Called just after puppeting has been completed and all
        Account<->Object links have been established.

        Note:
            You can use `self.account` and `self.sessions.get()` to get
            account and sessions at this point; the last entry in the
            list from `self.sessions.get()` is the latest Session
            puppeting this Object.

        """
        super(Character, self).at_post_puppet()

        # Log the connection
        sessions = self.sessions.get()
        if self.account and sessions:
            account = self.account
            session = sessions[0]
            log.info("{:>2}: {}@{}:{} logged in".format(session.sessid, account.key, session.address, self.key))

        # Display notifications
        for obj in self.contents:
            if hasattr(obj, "types"):
                types = obj.types.has("notifications")
                if types:
                    if types[0].notifications.all():
                        self.msg("|c{} vibrates|n: you have new notifications.".format(obj.get_display_name(self).capitalize()))

    def at_before_say(self, message, **kwargs):
        """
        Before the object says something.

        This hook is by default used by the 'say' and 'whisper'
        commands as used by this command it is called before the text
        is said/whispered and can be used to customize the outgoing
        text from the object. Returning `None` aborts the command.

        Args:
            message (str): The suggested say/whisper text spoken by self.
        Kwargs:
            whisper (bool): If True, this is a whisper rather than
                a say. This is sent by the whisper command by default.
                Other verbal commands could use this hook in similar
                ways.
            receivers (Object or iterable): If set, this is the target or targets for the say/whisper.

        Returns:
            message (str): The (possibly modified) text to be spoken.

        """
        # Escape | and {} (color codes and mapping)
        message = message.replace("|", "||")
        return super(Character, self).at_before_say(message)

    def at_say(self, speech, **kwargs):
        """Say something."""
        if kwargs.get("whisper"):
            msg_self = "You whisper to {all_receivers}: {speech}"
            msg_receivers = "{object} whispers to you: {speech}"
            msg_location = None
        else:
            msg_self = "You say: {speech}"
            msg_receivers = ""
            msg_location = "{object} says: {speech}"
        super(Character, self).at_say(speech, msg_self=msg_self,
                msg_location=msg_location, msg_receivers=msg_receivers)

    def display_turns(self, vehicle, crossroad):
        """Called to display the list of available exits."""
        if vehicle.has_message("turns"):
            return

        vehicle.add_message("turns")
        direction = vehicle.db.direction
        exits = crossroad.db.exits
        sessions = self.sessions.get()
        if sessions:
            if any(session.protocol_flags.get(
                    "SCREENREADER", False) for session in sessions):
                # One session on the driver has SCREENREADER turned on
                msg = ""
                for dir, exit in exits.items():
                    if msg:
                        msg += "\n"

                    name = get_direction(dir)["name"].capitalize()
                    msg += "  {:<10} - {}".format(name, exit["name"])
            else:
                # Create the diagram to represent the crossroad
                msg = MAP.format(
                        fl="|" if 6 in exits else " ",
                        fn="N  - " + exits[6]["name"] if 6 in exits else "",
                        erl="/" if 7 in exits else " ",
                        ern="NE - " + exits[7]["name"] if 7 in exits else "",
                        ell="\\" if 5 in exits else " ",
                        eln="NW - " + exits[5]["name"] if 5 in exits else "",
                        rl="-" if 0 in exits else " ",
                        rn="E  - " + exits[0]["name"] if 0 in exits else "",
                        ll="-" if 4 in exits else " ",
                        ln="W  - " + exits[4]["name"] if 4 in exits else "",
                        hrl="\\" if 1 in exits else " ",
                        hrn="SE - " + exits[1]["name"] if 1 in exits else "",
                        hll="/" if 3 in exits else " ",
                        hln="SW - " + exits[3]["name"] if 3 in exits else "",
                        bl="|" if 2 in exits else " ",
                        bn="S  - " + exits[2]["name"] if 2 in exits else "",
                )

            self.msg(msg)

    def pre_turn(self, vehicle, crossroad):
        """Called to have the driver make a decision regarding turning."""
        from world.log import main as log
        log.debug("Calling pre_turn X={} Y={} direciton={} crossroad={} {}".format(round(vehicle.db.coords[0], 3), round(vehicle.db.coords[1], 3), vehicle.db.direction, vehicle.db.next_crossroad, crossroad))

        # Call the 'pre_turn' event on the driver
        self.callbacks.call("pre_turn", self, vehicle, crossroad)

        # Call the pre_turn behavior on driver
        if "driver" in self.behaviors:
            self.behaviors["driver"].pre_turn(self, vehicle)
