import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from skrub._dataframe._polars import POLARS_SETUP
from skrub._multi_agg_joiner import MultiAggJoiner


@pytest.fixture
def main_table():
    df = pd.DataFrame(
        {
            "userId": [1, 1, 1, 2, 2, 2],
            "movieId": [1, 3, 6, 318, 6, 1704],
            "rating": [4.0, 4.0, 4.0, 3.0, 2.0, 4.0],
            "genre": ["drama", "drama", "comedy", "sf", "comedy", "sf"],
        }
    )
    return df


MODULES = [pd]
ASSERT_TUPLES = [(pd, assert_frame_equal)]

if POLARS_SETUP:
    import polars as pl
    from polars.testing import assert_frame_equal as assert_frame_equal_pl

    MODULES.append(pl)
    ASSERT_TUPLES.append((pl, assert_frame_equal_pl))


@pytest.mark.parametrize("use_X_placeholder", [False, True])
@pytest.mark.parametrize(
    "px, assert_frame_equal_",
    ASSERT_TUPLES,
)
def test_simple_fit_transform(main_table, use_X_placeholder, px, assert_frame_equal_):
    main_table = px.DataFrame(main_table)
    aux = [main_table, main_table] if not use_X_placeholder else ["X", "X"]

    multi_agg_joiner = MultiAggJoiner(
        aux_tables=aux,
        main_keys=[["userId"], ["movieId"]],
        aux_keys=[["userId"], ["movieId"]],
        cols=[["rating", "genre"], ["rating"]],
        suffixes=["_user", "_movie"],
    )

    main_user_movie = multi_agg_joiner.fit_transform(main_table)

    expected = px.DataFrame(
        {
            "userId": [1, 1, 1, 2, 2, 2],
            "movieId": [1, 3, 6, 318, 6, 1704],
            "rating": [4.0, 4.0, 4.0, 3.0, 2.0, 4.0],
            "genre": ["drama", "drama", "comedy", "sf", "comedy", "sf"],
            "genre_mode_user": ["drama", "drama", "drama", "sf", "sf", "sf"],
            "rating_mean_user": [4.0, 4.0, 4.0, 3.0, 3.0, 3.0],
            "rating_mean_movie": [4.0, 4.0, 3.0, 3.0, 3.0, 4.0],
        }
    )
    assert_frame_equal_(main_user_movie, expected)


@pytest.mark.parametrize("px", MODULES)
def test_X_placeholder(main_table, px):
    main_table = px.DataFrame(main_table)

    multi_agg_joiner = MultiAggJoiner(
        aux_tables=["X", main_table],
        keys=[["userId"], ["userId"]],
    )
    multi_agg_joiner.fit_transform(main_table)

    multi_agg_joiner = MultiAggJoiner(
        aux_tables=["X", "X"],
        keys=[["userId"], ["userId"]],
    )
    multi_agg_joiner.fit_transform(main_table)

    multi_agg_joiner = MultiAggJoiner(
        aux_tables=[main_table, main_table, "X", main_table],
        keys=[["userId"], ["userId"], ["userId"], ["userId"]],
    )
    multi_agg_joiner.fit_transform(main_table)


@pytest.mark.parametrize("px", MODULES)
def test_check_dataframes(main_table, px):
    main_table = px.DataFrame(main_table)

    # Check aux_tables isn't an array
    multi_agg_joiner = MultiAggJoiner(
        aux_tables=main_table,
        keys=["userId"],
    )
    with pytest.raises(
        ValueError,
        match=r"(?=must be an iterable containing dataframes and/or the string 'X')",
    ):
        multi_agg_joiner.fit_transform(main_table)

    # Check aux_tables is not a dataframe or "X"
    multi_agg_joiner = MultiAggJoiner(
        aux_tables=[1],
        keys=["userId"],
    )
    with pytest.raises(
        ValueError,
        match=r"(?=must be an iterable containing dataframes and/or the string 'X')",
    ):
        multi_agg_joiner.fit_transform(main_table)


@pytest.mark.skipif(not POLARS_SETUP, reason="Polars not available.")
@pytest.mark.parametrize("px", MODULES)
def test_check_wrong_aux_table_type(main_table, px):
    other_px = pd if px is pl else pl
    main_table = px.DataFrame(main_table)
    aux_table = other_px.DataFrame(main_table)

    # Check aux_tables is pandas when X is polars or the opposite
    multi_agg_joiner = MultiAggJoiner(
        aux_tables=[aux_table],
        keys=["userId"],
    )
    wanted_type = "Pandas" if px == pd else "Polars"
    with pytest.raises(
        TypeError, match=rf"All `aux_tables` must be {wanted_type} dataframes."
    ):
        multi_agg_joiner.fit_transform(main_table)


@pytest.mark.parametrize("px", MODULES)
def test_keys(main_table, px):
    main_table = px.DataFrame(main_table)

    # Check only keys
    multi_agg_joiner = MultiAggJoiner(
        aux_tables=[main_table],
        keys=["userId"],
    )
    multi_agg_joiner.fit_transform(main_table)

    # Check multiple keys
    multi_agg_joiner = MultiAggJoiner(
        aux_tables=[main_table],
        keys=["userId", "movieId"],
    )
    multi_agg_joiner.fit_transform(main_table)

    # Check no keys at all
    multi_agg_joiner = MultiAggJoiner(
        aux_tables=[main_table],
    )
    error_msg = r"Must pass EITHER `keys`, OR \(`main_keys` AND `aux_keys`\)."
    with pytest.raises(ValueError, match=error_msg):
        multi_agg_joiner.fit_transform(main_table)

    # Check multiple main_keys and aux_keys, same length
    multi_agg_joiner = MultiAggJoiner(
        aux_tables=[main_table],
        main_keys=["userId", "movieId"],
        aux_keys=["userId", "movieId"],
    )
    multi_agg_joiner.fit_transform(main_table)
    # aux_keys_ is 2d since we iterate over it
    assert multi_agg_joiner._main_keys == [["userId", "movieId"]]
    assert multi_agg_joiner._aux_keys == [["userId", "movieId"]]

    # Check too many main_keys
    multi_agg_joiner = MultiAggJoiner(
        aux_tables=[main_table],
        main_keys=["userId", "movieId"],
        aux_keys=["userId"],
    )
    with pytest.raises(
        ValueError,
        match=(
            r"(?=.*`main_keys` and `aux_keys` elements have different lengths at"
            r" position 0)"
        ),
    ):
        multi_agg_joiner.fit_transform(main_table)

    # Check too many aux_keys
    multi_agg_joiner = MultiAggJoiner(
        aux_tables=[main_table],
        main_keys=["userId"],
        aux_keys=["userId", "movieId"],
    )
    with pytest.raises(
        ValueError, match=r"(?=.*Cannot join on different numbers of columns)"
    ):
        multi_agg_joiner.fit_transform(main_table)

    # Check providing keys and extra main_keys
    multi_agg_joiner = MultiAggJoiner(
        aux_tables=[main_table],
        keys=["userId"],
        main_keys=["userId"],
    )
    with pytest.raises(ValueError, match=r"(?=.*not a combination of both.)"):
        multi_agg_joiner.fit_transform(main_table)

    # Check providing key and extra aux_keys
    multi_agg_joiner = MultiAggJoiner(
        aux_tables=[main_table],
        keys=["userId"],
        aux_keys=["userId"],
    )
    with pytest.raises(ValueError, match=r"(?=.*not a combination of both.)"):
        multi_agg_joiner.fit_transform(main_table)

    # Check main_keys doesn't exist in table
    multi_agg_joiner = MultiAggJoiner(
        aux_tables=[main_table],
        main_keys=["wrong_key"],
        aux_keys=["userId"],
    )
    error_msg = r"(?=.*columns cannot be used because they do not exist)"
    with pytest.raises(ValueError, match=error_msg):
        multi_agg_joiner.fit_transform(main_table)

    # Check aux_keys doesn't exist in table
    multi_agg_joiner = MultiAggJoiner(
        aux_tables=[main_table],
        main_keys=["userId"],
        aux_keys=["wrong_key"],
    )
    error_msg = r"(?=.*columns cannot be used because they do not exist)"
    with pytest.raises(ValueError, match=error_msg):
        multi_agg_joiner.fit_transform(main_table)

    # Check keys multiple tables
    multi_agg_joiner = MultiAggJoiner(
        aux_tables=[main_table, main_table],
        keys=[["userId"], ["userId"]],
    )
    multi_agg_joiner.fit_transform(main_table)

    # Check wrong aux_keys lenght
    multi_agg_joiner = MultiAggJoiner(
        aux_tables=[main_table, main_table],
        main_keys=[["userId"], ["userId"]],
        aux_keys=[["userId"]],
    )
    error_msg = r"(?=The length of `aux_keys` must match the number of `aux_tables`)"
    with pytest.raises(ValueError, match=error_msg):
        multi_agg_joiner.fit_transform(main_table)

    # Check wrong main_keys lenght
    multi_agg_joiner = MultiAggJoiner(
        aux_tables=[main_table, main_table],
        main_keys=[["userId"]],
        aux_keys=[["userId"], ["userId"]],
    )
    error_msg = r"(?=The length of `main_keys` must match the number of `aux_tables`)"
    with pytest.raises(ValueError, match=error_msg):
        multi_agg_joiner.fit_transform(main_table)


@pytest.mark.parametrize("px", MODULES)
def test_cols(main_table, px):
    main_table = px.DataFrame(main_table)

    # Check providing one cols
    multi_agg_joiner = MultiAggJoiner(
        aux_tables=[main_table],
        keys=["userId"],
        cols=["rating"],
    )
    multi_agg_joiner.fit_transform(main_table)
    assert multi_agg_joiner._cols == [["rating"]]

    # Check providing one col for each aux_tables
    multi_agg_joiner = MultiAggJoiner(
        aux_tables=[main_table, main_table],
        keys=[["userId"], ["userId"]],
        cols=[["rating"], ["rating"]],
    )
    multi_agg_joiner.fit_transform(main_table)
    assert multi_agg_joiner._cols == [["rating"], ["rating"]]

    # Check providing too many cols
    multi_agg_joiner = MultiAggJoiner(
        aux_tables=[main_table],
        keys=["userId"],
        cols=[["rating"], ["rating"]],
    )
    error_msg = r"The number of provided cols must match the number of"
    with pytest.raises(ValueError, match=error_msg):
        multi_agg_joiner.fit_transform(main_table)

    # Check cols not in table
    multi_agg_joiner = MultiAggJoiner(
        aux_tables=[main_table],
        keys=["userId"],
        cols=[["wrong_col"]],
    )
    error_msg = r"(?=.*columns cannot be used because they do not exist)"
    with pytest.raises(ValueError, match=error_msg):
        multi_agg_joiner.fit_transform(main_table)


@pytest.mark.parametrize("px", MODULES)
def test_operations(main_table, px):
    main_table = px.DataFrame(main_table)

    # Check one operation
    multi_agg_joiner = MultiAggJoiner(
        aux_tables=[main_table],
        keys=["userId"],
        cols=["rating"],
        operations=["mean"],
    )
    multi_agg_joiner.fit_transform(main_table)
    assert multi_agg_joiner._operations == [["mean"]]

    # Check list of operations
    multi_agg_joiner = MultiAggJoiner(
        aux_tables=[main_table, main_table],
        keys=[["userId"], ["userId"]],
        cols=[["rating"], ["rating"]],
        operations="mean",
    )
    error_msg = r"Accepted inputs for operations are None, iterable of str"
    with pytest.raises(ValueError, match=error_msg):
        multi_agg_joiner.fit_transform(main_table)

    # Check one operation for each aux table
    multi_agg_joiner = MultiAggJoiner(
        aux_tables=[main_table, main_table],
        keys=[["userId"], ["userId"]],
        cols=[["rating"], ["rating"]],
        operations=[["mean"], ["mean"]],
    )
    multi_agg_joiner.fit_transform(main_table)
    assert multi_agg_joiner._operations == [["mean"], ["mean"]]

    # Check badly formatted operation
    multi_agg_joiner = MultiAggJoiner(
        aux_tables=[main_table, main_table],
        keys=[["userId"], ["userId"]],
        cols=[["rating"], ["rating"]],
        operations=["mean", "mean", "mode"],
    )
    error_msg = r"The number of provided operations must match the number of tables"
    with pytest.raises(ValueError, match=error_msg):
        multi_agg_joiner.fit_transform(main_table)

    # Check one and two operations
    multi_agg_joiner = MultiAggJoiner(
        aux_tables=[main_table, main_table],
        keys=[["userId"], ["userId"]],
        cols=[["rating"], ["rating"]],
        operations=[["mean"], ["mean", "mode"]],
    )
    multi_agg_joiner.fit_transform(main_table)
    assert multi_agg_joiner._operations == [["mean"], ["mean", "mode"]]


@pytest.mark.parametrize("px", MODULES)
def test_suffixes(main_table, px):
    main_table = px.DataFrame(main_table)

    # check default suffixes with multiple tables
    multi_agg_joiner = MultiAggJoiner(
        aux_tables=[main_table, main_table],
        keys=[["userId"], ["userId"]],
        cols=[["rating"], ["rating"]],
    )
    multi_agg_joiner.fit_transform(main_table)
    assert multi_agg_joiner._suffixes == ["_0", "_1"]

    # check suffixes when defined
    multi_agg_joiner = MultiAggJoiner(
        aux_tables=[main_table, main_table],
        keys=[["userId"], ["userId"]],
        cols=[["rating"], ["rating"]],
        suffixes=["_this", "_works"],
    )
    multi_agg_joiner.fit_transform(main_table)
    assert multi_agg_joiner._suffixes == ["_this", "_works"]

    # check too many suffixes
    multi_agg_joiner = MultiAggJoiner(
        aux_tables=[main_table, main_table],
        keys=[["userId"], ["userId"]],
        cols=[["rating"], ["rating"]],
        suffixes=["_0", "_1", "_2"],
    )
    error_msg = (
        r"The number of provided suffixes must match the number of tables in"
        r" `aux_tables`. Got 3 suffixes and 2 aux_tables."
    )
    with pytest.raises(ValueError, match=error_msg):
        multi_agg_joiner.fit_transform(main_table)

    # check suffixes not str
    multi_agg_joiner = MultiAggJoiner(
        aux_tables=[main_table],
        keys=[["userId"]],
        cols=[["rating"]],
        suffixes=[1],
    )
    error_msg = r"All suffixes must be strings."
    with pytest.raises(ValueError, match=error_msg):
        multi_agg_joiner.fit_transform(main_table)


@pytest.mark.parametrize("px", MODULES)
def test_tuple_parameters(main_table, px):
    main_table = px.DataFrame(main_table)
    multi_agg_joiner = MultiAggJoiner(
        aux_tables=(main_table, main_table),
        keys=(("userId",), ("userId",)),
        cols=(("rating",), ("rating",)),
        operations=(("mean",), ("mean", "mode")),
        suffixes=("_1", "_2"),
    )
    multi_agg_joiner.fit_transform(main_table)


@pytest.mark.parametrize("px", MODULES)
def test_not_fitted_dataframe(main_table, px):
    main_table = px.DataFrame(main_table)
    not_main = px.DataFrame({"wrong": [1, 2, 3], "dataframe": [4, 5, 6]})

    multi_agg_joiner = MultiAggJoiner(
        aux_tables=[main_table],
        keys=["userId"],
    )
    multi_agg_joiner.fit(main_table)
    error_msg = r"(?=.*columns cannot be used because they do not exist)"
    with pytest.raises(ValueError, match=error_msg):
        multi_agg_joiner.transform(not_main)
