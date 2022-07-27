from datetime import datetime
from pathlib import Path

import pytest
from datalad.distribution.dataset import Dataset
from datalad.tests.test_utils_testrepos import BasicGitTestRepo
from datalad.tests.utils_pytest import (
    assert_raises,
    assert_str_equal,
    with_tree
)
from datalad.utils import rmtemp

from ..tree import Tree, DatasetTree, build_excluded_node_func

"""Tests for the ``datalad tree`` command."""


# ============================ Helper functions ===============================

def create_temp_dir_tree(tree_dict: dict) -> Path:
    """
    Create a temporary directory tree.

    This is a shim for the ``with_tree()`` decorator so it can be used
    in a module-scoped pytest fixture.

    Parameters
    ----------
    tree_dict: dict
        A dict describing a directory tree (see parameter of ``with_tree``)

    Returns
    -------
    Path
        Root directory of the newly created tree
    """
    # function to be decorated by 'with_tree'
    # just return the argument (will be the created temp path)
    identity_func = lambda d: d

    # give an informative name to the lambda function, since
    # it will be included in the name of the temp dir
    identity_func.__name__ = "test_tree"

    # call the 'with_tree' decorator to return the path
    # of the created temp dir root, without deleting it
    temp_dir_root = with_tree(tree_dict, delete=False)(identity_func)()
    return Path(temp_dir_root).resolve()


@pytest.fixture(scope="module")
def path_no_ds():
    """Fixture for creating a temporary directory tree (**without** datasets)
    to be used in tests.

    Returns
    -------
    Path
        Root directory of the newly created tree
    """
    dir_tree = {
        "root": {
            ".dir3": {
                "dir3_file0": '',
                ".dir3_file1": '',
            },
            "dir0": {},
            "dir1": {
                "dir1_file0": '',
            },
            "dir2": {
                "dir2_dir0": {},
                "dir2_dir1": {
                    "dir2_dir1_file0": '',
                },
                "dir2_dir2": {
                    "dir2_dir2_file0": '',
                    "dir2_dir2_file1": '',
                },
                "dir2_file0": '',
                "dir2_file1": '',
            },
            ".file2": '',
            "file0": '',
            "file1": '',
        }
    }

    temp_dir_root = create_temp_dir_tree(dir_tree)
    yield temp_dir_root
    rmtemp(temp_dir_root)
    assert not temp_dir_root.exists()


@pytest.fixture(scope="module")
def path_ds():
    """Fixture for creating a temporary directory tree (**including** datasets)
    to be used in tests.

    Returns
    -------
    Path
        Root directory of the newly created tree
    """
    ds_tree = {
        "root": {
            "superds0": {
                "sd0_file0": "",
                "sd0_subds0": {
                    "sd0_sub0_subds0": {}
                }
            },
            "superds1": {
                "sd1_file0": "",
                "sd1_dir0": {
                    "sd1_d0_repo0": {},
                    "sd1_d0_subds0": {},
                },
                "sd1_ds0": {},  # not registered as subdataset
                "sd1_subds0": {},  # not installed (drop all)
            },
            # plain git repo (contents are defined in BasicGitTestRepo)
            "repo0": {},
            "file0": "",
        }
    }

    temp_dir_root = create_temp_dir_tree(ds_tree)

    # create datasets / repos
    root = temp_dir_root / "root"
    BasicGitTestRepo(path=root / "repo0", puke_if_exists=False)
    superds0 = Dataset(root / "superds0").create(force=True)
    sd0_subds0 = superds0.create("sd0_subds0", force=True)
    sd0_subds0.create("sd0_sub0_subds0", force=True)
    superds1 = Dataset(root / "superds1").create(force=True)
    superds1.create(Path("sd1_dir0") / "sd1_d0_subds0", force=True)
    Dataset(root / "superds1" / "sd1_ds0").create(force=True)
    BasicGitTestRepo(
        path=root / "superds1" / "sd1_dir0" / "sd1_d0_repo0",
        puke_if_exists=False)
    sd1_subds0 = superds1.create("sd1_subds0", force=True)
    sd1_subds0.drop(what='all', reckless='kill', recursive=True)

    yield temp_dir_root

    # delete temp dir
    rmtemp(temp_dir_root)
    assert not temp_dir_root.exists()


@pytest.fixture(scope="class")
def inject_path_no_ds(request, path_no_ds):
    """
    Set ``path_no_ds`` fixture (root path of temp directory tree) as class
    attribute, to make it available to all tests in the class
    """
    request.cls.path = path_no_ds


@pytest.fixture(scope="class")
def inject_path_ds(request, path_ds):
    """
    Set ``path_ds`` fixture (root path of temp directory tree) as class
    attribute, to make it available to all tests in the class
    """
    request.cls.path = path_ds


def format_param_ids(val) -> str:
    """
    Helper to format pytest parameter IDs.

    If the parameter is a multiline string, we assume it is the
    parameter 'expected' (expected output of tree), and just
    give it a fixed ID (otherwise, it would be displayed in the
    parameter list as a long unreadable string).

    Parameters
    ----------
    val
        Parameter value
    """
    if isinstance(val, str) and "\n" in val:
        return "expected"


def build_param_matrix(matrix, params):
    """Turn inner dicts into lists (required by pytest parametrize)"""
    matrix_out = []
    for combination in matrix:
        matrix_out.append(
            # order of combinations does not matter
            [val for key, val in combination.items() if key in params]
        )
    return matrix_out


def pytest_generate_tests(metafunc):
    """Pytest helper to automatically configure parametrization.

    Avoids having to duplicate definition of parameter names and values
    across tests that use the same data.

    See: https://docs.pytest.org/en/7.1.x/example/parametrize.html#parametrizing-test-methods-through-per-class-configuration
    """
    if metafunc.cls:
        test_id = metafunc.function.__name__
        test_params_dict = metafunc.cls.params
        matrix = metafunc.cls.MATRIX
        if test_id in metafunc.cls.params:
            param_names = test_params_dict[test_id]
            metafunc.parametrize(
                param_names,
                build_param_matrix(matrix, param_names),
                ids=format_param_ids
            )

# ================================= Tests =====================================

def test_print_tree_fails_for_nonexistent_directory():
    """Obtain nonexistent directory by creating a temp dir and deleting it
    (may be safest method)"""
    dir_name = f"to_be_deleted_{datetime.now().timestamp()}"
    nonexistent_dir = Path(with_tree({dir_name: []})(lambda f: f)())
    with assert_raises(ValueError):
        Tree(nonexistent_dir, max_depth=1)


class TestTree:
    """Base class with tests that should run for all Tree configurations"""
    __test__ = False  # tells pytest to not collect tests in this class
    path = None  # will be set by the inject_* fixture to temp dir tree root

    # dict specifying multiple argument sets for a test method
    params = {
        "test_print_tree": [
            "depth", "include_files", "include_hidden", "expected_str"
        ],
        "test_print_stats": [
            "depth", "include_files", "include_hidden", "expected_stats_str"
        ]
    }


@pytest.mark.usefixtures("inject_path_no_ds")
class TestTreeWithoutDatasets(TestTree):
    """Test directory tree without any datasets"""

    __test__ = True

    # matrix holds combinations of parameters to be tested
    # and their expected results
    MATRIX = [
    {
        "depth": 1,
        "include_files": False,
        "include_hidden": False,
        "expected_stats_str": "0 datasets, 3 directories, 0 files",
        "expected_str": """
├── dir0/
├── dir1/
└── dir2/
"""
    },
    {
        "depth": 3,
        "include_files": False,
        "include_hidden": False,
        "expected_stats_str": "0 datasets, 6 directories, 0 files",
        "expected_str": """
├── dir0/
├── dir1/
└── dir2/
    ├── dir2_dir0/
    ├── dir2_dir1/
    └── dir2_dir2/
"""
    },
    {
        "depth": 1,
        "include_files": True,
        "include_hidden": False,
        "expected_stats_str": "0 datasets, 3 directories, 2 files",
        "expected_str": """
├── dir0/
├── dir1/
├── dir2/
├── file0
└── file1
"""
    },
    {
        "depth": 3,
        "include_files": True,
        "include_hidden": False,
        "expected_stats_str": "0 datasets, 6 directories, 8 files",
        "expected_str": """
├── dir0/
├── dir1/
│   └── dir1_file0
├── dir2/
│   ├── dir2_dir0/
│   ├── dir2_dir1/
│   │   └── dir2_dir1_file0
│   ├── dir2_dir2/
│   │   ├── dir2_dir2_file0
│   │   └── dir2_dir2_file1
│   ├── dir2_file0
│   └── dir2_file1
├── file0
└── file1
"""
    },
    {
        "depth": 1,
        "include_files": True,
        "include_hidden": True,
        "expected_stats_str": "0 datasets, 4 directories, 3 files",
        "expected_str": """
├── .dir3/
├── .file2
├── dir0/
├── dir1/
├── dir2/
├── file0
└── file1
"""
    },
    {
        "depth": 3,
        "include_files": True,
        "include_hidden": True,
        "expected_stats_str": "0 datasets, 7 directories, 11 files",
        "expected_str": """
├── .dir3/
│   ├── .dir3_file1
│   └── dir3_file0
├── .file2
├── dir0/
├── dir1/
│   └── dir1_file0
├── dir2/
│   ├── dir2_dir0/
│   ├── dir2_dir1/
│   │   └── dir2_dir1_file0
│   ├── dir2_dir2/
│   │   ├── dir2_dir2_file0
│   │   └── dir2_dir2_file1
│   ├── dir2_file0
│   └── dir2_file1
├── file0
└── file1
"""
    },
    {
        "depth": 1,
        "include_files": False,
        "include_hidden": True,
        "expected_stats_str": "0 datasets, 4 directories, 0 files",
        "expected_str": """
├── .dir3/
├── dir0/
├── dir1/
└── dir2/
"""
    },
    {
        "depth": 3,
        "include_files": False,
        "include_hidden": True,
        "expected_stats_str": "0 datasets, 7 directories, 0 files",
        "expected_str": """
├── .dir3/
├── dir0/
├── dir1/
└── dir2/
    ├── dir2_dir0/
    ├── dir2_dir1/
    └── dir2_dir2/
"""
    },
    ]

    def test_print_tree(
            self, depth, include_files, include_hidden, expected_str
    ):
        root = Path(self.path) / "root"
        tree = Tree(
            root, max_depth=depth,
            exclude_node_func=build_excluded_node_func(
                include_hidden=include_hidden, include_files=include_files
            ),
            skip_root=True  # skip the first line with the root directory
        )
        lines = tree.print_line()
        actual_res = "\n".join(line for line in lines) + "\n"
        expected_res = expected_str.lstrip("\n")  # strip first newline
        print("expected:")
        print(expected_res)
        print("actual:")
        print(actual_res)
        assert_str_equal(expected_res, actual_res)

    def test_print_stats(
            self, depth, include_files, include_hidden, expected_stats_str
    ):
        root = self.path / 'root'
        tree = Tree(
            root, max_depth=depth,
            exclude_node_func=build_excluded_node_func(
                include_hidden=include_hidden, include_files=include_files
            ),
        ).build()
        actual_res = tree.stats()
        expected_res = expected_stats_str
        assert_str_equal(expected_res, actual_res)

    @pytest.mark.parametrize(
        "root_dir_name", ["root/", "root/.", "root/./", "root/../root"]
    )
    def test_root_path_is_normalized(self, root_dir_name):
        """
        Test that root path in the first line of string output
        is normalized path
        """
        root = self.path / root_dir_name
        tree = Tree(root, max_depth=0)
        expected = str(self.path / "root")
        actual = next(tree.print_line())  # first line of tree output
        assert_str_equal(expected, actual)

    def test_tree_to_string(self):
        root = self.path / 'root'
        tree = Tree(root, 3)
        actual = tree.to_string()
        expected = "\n".join(tree._lines)
        assert_str_equal(expected, actual)

    def test_print_tree_depth_zero(self):
        root = self.path / "root"
        tree = Tree(
            root,
            max_depth=0,
            # including files should have no effect
            exclude_node_func=build_excluded_node_func(include_files=True)
        )
        actual = tree.to_string()
        expected = str(root)
        assert_str_equal(expected, actual)


@pytest.mark.usefixtures("inject_path_ds")
class TestTreeWithDatasets(TestTree):
    """Test directory tree with datasets"""

    __test__ = True

    MATRIX = [
    {
        "depth": 1,
        "expected_stats_str": "2 datasets, 1 directory, 0 files",
        "expected_str": """
├── repo0/
├── superds0/  [DS~0]
└── superds1/  [DS~0]
""",
    },
    {
        "depth": 4,
        "expected_stats_str": "7 datasets, 3 directories, 0 files",
        "expected_str": """
├── repo0/
├── superds0/  [DS~0]
│   └── sd0_subds0/  [DS~1]
│       └── sd0_sub0_subds0/  [DS~2]
└── superds1/  [DS~0]
    ├── sd1_dir0/
    │   ├── sd1_d0_repo0/
    │   └── sd1_d0_subds0/  [DS~1]
    ├── sd1_ds0/  [DS~0]
    └── sd1_subds0/  [DS~1, not installed]
""",
    },
    ]

    params = {
        "test_print_tree": [
            "depth", "expected_str"
        ],
        "test_print_stats": [
            "depth", "expected_stats_str"
        ]
    }

    def test_print_tree(
            self, depth, expected_str
    ):
        root = self.path / "root"
        tree = Tree(
            root, max_depth=depth,
            skip_root=True  # skip the first line with the root directory
        )
        lines = tree.print_line()
        actual_res = "\n".join(l for l in lines) + "\n"
        expected_res = expected_str.lstrip("\n")  # strip first newline
        assert_str_equal(expected_res, actual_res)

    def test_print_stats(
            self, depth, expected_stats_str
    ):
        root = self.path / 'root'
        tree = Tree(root, max_depth=depth).build()
        actual_res = tree.stats()
        expected_res = expected_stats_str
        assert_str_equal(expected_res, actual_res)


@pytest.mark.usefixtures("inject_path_ds")
class TestDatasetTree(TestTree):
    """Test dataset tree with max_dataset_depth parameter"""

    __test__ = True

    MATRIX = [
    {
        "dataset_depth": 0,
        "depth": 0,
        "expected_stats_str": "3 datasets, 0 directories, 0 files",
        "expected_str": """
├── superds0/  [DS~0]
└── superds1/  [DS~0]
    └── sd1_ds0/  [DS~0]
"""
    },
    {
        "dataset_depth": 0,
        "depth": 1,
        "expected_stats_str": "3 datasets, 1 directory, 0 files",
        "expected_str": """
├── superds0/  [DS~0]
└── superds1/  [DS~0]
    ├── sd1_dir0/
    └── sd1_ds0/  [DS~0]
"""
    },
    {
        "dataset_depth": 1,
        "depth": 0,
        "expected_stats_str": "6 datasets, 1 directory, 0 files",
        "expected_str": """
├── superds0/  [DS~0]
│   └── sd0_subds0/  [DS~1]
└── superds1/  [DS~0]
    ├── sd1_dir0/
    │   └── sd1_d0_subds0/  [DS~1]
    ├── sd1_ds0/  [DS~0]
    └── sd1_subds0/  [DS~1, not installed]
"""
    },
    {
        "dataset_depth": 1,
        "depth": 2,
        "expected_stats_str": "6 datasets, 2 directories, 0 files",
        "expected_str": """
├── superds0/  [DS~0]
│   └── sd0_subds0/  [DS~1]
└── superds1/  [DS~0]
    ├── sd1_dir0/
    │   ├── sd1_d0_repo0/
    │   └── sd1_d0_subds0/  [DS~1]
    ├── sd1_ds0/  [DS~0]
    └── sd1_subds0/  [DS~1, not installed]
"""
    },
    ]

    params = {
        "test_print_tree": [
            "dataset_depth", "depth", "expected_str"
        ],
        "test_print_stats": [
            "dataset_depth", "depth", "expected_stats_str"
        ]
    }

    def test_print_tree(
            self, dataset_depth, depth, expected_str
    ):
        root = self.path / "root"
        tree = DatasetTree(
            root, max_depth=depth, max_dataset_depth=dataset_depth,
            skip_root=True)
        lines = tree.print_line()
        actual_res = "\n".join(l for l in lines) + "\n"
        expected_res = expected_str.lstrip("\n")  # strip first newline
        print("expected:")
        print(expected_res)
        print("actual:")
        print(actual_res)
        assert_str_equal(expected_res, actual_res)

    def test_print_stats(
            self, dataset_depth, depth, expected_stats_str
    ):
        root = self.path / 'root'
        tree = DatasetTree(
            root, max_depth=depth, max_dataset_depth=dataset_depth
        ).build()
        actual_res = tree.stats()
        expected_res = expected_stats_str
        assert_str_equal(expected_res, actual_res)
