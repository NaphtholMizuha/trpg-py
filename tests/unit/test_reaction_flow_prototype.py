from src.executors.reaction_flow_prototype import ReactionFlowPrototype, demo_run


def test_magic_missile_without_reaction():
    state = demo_run(["skip"])
    aldera = state.combatants["Aldera"]
    malik = state.combatants["Malik"]

    assert state.completed is True
    assert aldera.hp == 35
    assert malik.spell_slots[1] == 3
    assert aldera.spell_slots[1] == 4
    assert "Magic Missile deals 9 force damage to Aldera." in state.log


def test_magic_missile_with_shield():
    state = demo_run(["cast_shield", "skip"])
    aldera = state.combatants["Aldera"]
    malik = state.combatants["Malik"]

    assert state.completed is True
    assert aldera.hp == 44
    assert aldera.spell_slots[1] == 3
    assert aldera.reaction_available is False
    assert malik.spell_slots[3] == 2
    assert "Magic Missile is negated by Shield." in state.log


def test_magic_missile_with_shield_and_counterspell():
    state = demo_run(["cast_shield", "cast_counterspell"])
    aldera = state.combatants["Aldera"]
    malik = state.combatants["Malik"]

    assert state.completed is True
    assert aldera.hp == 35
    assert aldera.spell_slots[1] == 3
    assert malik.spell_slots[3] == 1
    assert malik.reaction_available is False
    assert "Counterspell succeeds automatically; Shield is cancelled." in state.log


def test_engine_stops_and_waits_for_choice():
    engine = ReactionFlowPrototype()
    state = engine.create_magic_missile_state()

    engine.advance(state)

    assert state.completed is False
    assert state.pending_choice is not None
    assert state.pending_choice.key == "shield"
