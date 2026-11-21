"""Consent tiers. Consent is collected before any behavioral tracking starts.

Students can say yes to the basics without saying yes to everything.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Tier(StrEnum):
    ESSENTIAL = "essential"                    # answers, correctness, help level, time per item, mastery
    LEARNING_BEHAVIOR = "learning_behavior"    # hesitation, edits, hint timing, session rhythm
    VOICE_IMAGES = "voice_images"              # voice explain-back, photos of paper work
    RESEARCH = "research"                      # pooled, anonymized data (off until accepted)


class ConsentError(ValueError):
    pass


@dataclass(frozen=True)
class ConsentState:
    """What the student agreed to.

    Minors (under 18): no research tier unless a guardian consented; until guardian consent arrives (where the
    law requires it) the student only gets a demo subject and NO personal data beyond the account is stored.
    """

    granted: frozenset[Tier] = field(default_factory=lambda: frozenset({Tier.ESSENTIAL}))
    is_minor: bool = False
    guardian_required: bool = False
    guardian_consented: bool = False

    @property
    def demo_only(self) -> bool:
        return self.is_minor and self.guardian_required and not self.guardian_consented

    def allows(self, tier: Tier) -> bool:
        if self.demo_only:
            return False
        if tier is Tier.ESSENTIAL:
            return True
        return tier in self.granted

    def grant(self, tier: Tier) -> ConsentState:
        if tier is Tier.RESEARCH and self.is_minor and not self.guardian_consented:
            raise ConsentError("The research tier needs guardian consent for minors.")
        return ConsentState(self.granted | {tier, Tier.ESSENTIAL}, self.is_minor, self.guardian_required,
                            self.guardian_consented)

    def revoke(self, tier: Tier) -> ConsentState:
        if tier is Tier.ESSENTIAL:
            raise ConsentError("Essential data is needed for the product to work; delete the account instead.")
        return ConsentState(self.granted - {tier}, self.is_minor, self.guardian_required, self.guardian_consented)

    def with_guardian_consent(self) -> ConsentState:
        return ConsentState(self.granted, self.is_minor, self.guardian_required, True)

    @classmethod
    def default(cls, *, birth_year: int | None, current_year: int, adult_age: int = 18,
                guardian_required: bool = True) -> ConsentState:
        """Age gate: birth year only. Only the essential tier is on until the student answers.

        Legal thresholds differ by country (open question in the design doc): `adult_age` and `guardian_required`
        are per-country settings to confirm with a legal advisor before launch.
        """
        is_minor = birth_year is not None and (current_year - birth_year) < adult_age
        return cls(frozenset({Tier.ESSENTIAL}), is_minor=is_minor, guardian_required=is_minor and guardian_required)
