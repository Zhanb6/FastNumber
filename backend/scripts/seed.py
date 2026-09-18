"""Seed demo data: 50 participants (Kazakh/Russian names) + a demo draw. Idempotent.

python -m scripts.seed
"""

import asyncio
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Draw, DrawStatus, Participant
from app.services import audit
from app.services.notify import notify_live
from app.services.registration import create_participant
from app.services.settings import get_settings

DEMO_DRAW_TITLE = "Демо-розыгрыш"
DEMO_DRAW_PRIZE = "Демо-приз"

FIRST_NAMES = [
    "Айгерим", "Данияр", "Алия", "Ерлан", "Жанна", "Нурлан", "Дана", "Арман", "Сауле", "Бауыржан",
    "Мадина", "Тимур", "Асель", "Алексей", "Мария", "Дмитрий", "Анна", "Сергей", "Елена", "Иван",
    "Гүлнар", "Әлібек", "Назерке", "Қайрат", "Айнұр",
]  # fmt: skip
LAST_NAMES = [
    "Ахметова", "Сериков", "Нурланова", "Абдуллин", "Касымова", "Жумабеков", "Оспанова", "Ермеков",
    "Бекова", "Сулейменов", "Иванова", "Петров", "Смирнова", "Кузнецов", "Попова", "Соколов",
    "Лебедева", "Морозов", "Волкова", "Новиков", "Тоқтарова", "Сағынов", "Мұратова", "Ыдырысов",
    "Әбдіқадырова",
]  # fmt: skip


def demo_participants() -> list[tuple[str, str]]:
    people: list[tuple[str, str]] = []
    for i in range(50):
        first = FIRST_NAMES[i % len(FIRST_NAMES)]
        last = LAST_NAMES[(i * 7 + i // len(FIRST_NAMES)) % len(LAST_NAMES)]
        people.append((first, last))
    return people


async def seed(session: AsyncSession, *, admin_login: str = "seed") -> dict[str, int]:
    """Create participants and the demo draw unless they already exist. Commits."""
    settings = await get_settings(session)
    created = {"participants": 0, "draws": 0}

    has_participant = (await session.execute(select(Participant.id).limit(1))).scalar_one_or_none()
    if has_participant is None:
        for first, last in demo_participants():
            await create_participant(
                session,
                settings,
                first_name=first,
                last_name=last,
                phone=None,
                email=None,
                company=None,
                ip=None,
                user_agent="seed",
                admin_login=admin_login,
            )
            created["participants"] += 1

    demo = (
        await session.execute(select(Draw).where(Draw.title == DEMO_DRAW_TITLE).limit(1))
    ).scalar_one_or_none()
    if demo is None:
        session.add(
            Draw(
                position=1,
                title=DEMO_DRAW_TITLE,
                prize=DEMO_DRAW_PRIZE,
                description="Тестовый розыгрыш для проверки экрана и админки",
                status=DrawStatus.DRAFT,
            )
        )
        created["draws"] += 1
        await notify_live(session, "seed")

    if created["participants"] or created["draws"]:
        audit.log(
            session,
            "SEED",
            entity_type="system",
            admin_login=admin_login,
            metadata=created,
        )
    await session.commit()
    return created


async def main() -> int:
    from app.db import async_session, engine
    from app.startup import ensure_singletons

    async with async_session() as session:
        await ensure_singletons(session)
        await session.commit()
        created = await seed(session, admin_login="cli")
    await engine.dispose()
    if not created["participants"] and not created["draws"]:
        print("Seed skipped: participants or demo draw already exist")
    else:
        print(f"Seeded {created['participants']} participants, {created['draws']} demo draw(s)")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
