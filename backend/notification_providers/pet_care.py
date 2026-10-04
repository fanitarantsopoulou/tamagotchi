"""Pet care notifications: the pet asks for help before things get bad."""

from datetime import datetime
from typing import List

import pet
from notification_providers.base import Notice, NotificationProvider

COOLDOWN_HOURS = 3  # at most one nudge of each kind every few hours


class PetCareProvider(NotificationProvider):
    name = "pet"

    def check(self, now: datetime) -> List[Notice]:
        state = pet.get_state()
        name = state["name"]
        if not state["alive"]:
            return [Notice("pet-dead", f"💀 Το {name} δεν τα κατάφερε... Άνοιξε το Tamagotchi και πάτα B για νέο αυγό.", 24, urgent=True)]
        if state["stage"] == "egg" or state["sleeping"]:
            return []

        notices = []
        if state["health"] < 30:
            notices.append(Notice("pet-critical", f"🚨 Bestie, δεν είμαι καθόλου καλά (υγεία {state['health']}%). Χρειάζομαι φροντίδα τώρα!", COOLDOWN_HOURS, urgent=True))
        elif state["mood"] == "sick":
            notices.append(Notice("pet-sick", "🤒 Νιώθω άρρωστο... Καθάρισέ με και τάισέ με λίγο;", COOLDOWN_HOURS))
        if state["hunger"] < 25:
            notices.append(Notice("pet-hungry", "🍙 Πεινάωωω! Ένα σνακάκι;", COOLDOWN_HOURS))
        if state["poops"] >= 2:
            notices.append(Notice("pet-dirty", "💩 Εδώ μέσα χρειάζεται καθάρισμα, OMG.", COOLDOWN_HOURS))
        return notices
