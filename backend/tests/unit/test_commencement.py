from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from app.domain.calculation.commencement import CommencementUndetermined, determine_commencement


def test_case_01_nor_plus_6_before_all_fast():
    """Test 1 (brief section 78): NOR + 6 occurs before All Fast/Securely Moored ->
    NOR + 6 is selected."""
    nor = datetime(2026, 5, 28, 2, 6)
    moored = datetime(2026, 5, 28, 11, 42)
    result = determine_commencement(nor_tendered=nor, securely_moored=moored, allowance_hours=Decimal(6))
    assert result.selected == datetime(2026, 5, 28, 8, 6)
    assert result.rule_applied == "NOR_ALLOWANCE / Whichever Occurs First"


def test_case_02_all_fast_before_nor_plus_6():
    """Test 2: All Fast/Securely Moored occurs before NOR + 6 -> Securely Moored wins."""
    nor = datetime(2026, 5, 28, 2, 6)
    moored = datetime(2026, 5, 28, 5, 0)
    result = determine_commencement(nor_tendered=nor, securely_moored=moored, allowance_hours=Decimal(6))
    assert result.selected == moored
    assert result.selected_label == "Securely Moored"
    assert result.rule_applied == "SECURELY_MOORED_TRIGGER / Whichever Occurs First"


def test_commencement_undetermined_without_any_trigger():
    with pytest.raises(CommencementUndetermined):
        determine_commencement(nor_tendered=None, securely_moored=None, allowance_hours=Decimal(6))


def test_commencement_records_all_candidates():
    nor = datetime(2026, 5, 28, 2, 6)
    moored = datetime(2026, 5, 28, 11, 42)
    result = determine_commencement(nor_tendered=nor, securely_moored=moored, allowance_hours=Decimal(6))
    assert len(result.candidates) == 2
