import pytest

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import validate_csrf


@pytest.mark.parametrize("token", ["é", "a." + "é" * 64, "a" * 257])
def test_malformed_csrf_is_forbidden_instead_of_an_internal_error(token):
    with pytest.raises(AppError) as error:
        validate_csrf(token, token, get_settings())
    assert error.value.status == 403
