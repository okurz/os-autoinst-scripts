# Copyright SUSE LLC
import pathlib
from unittest.mock import MagicMock

from pytest_mock import MockerFixture
from typer.testing import CliRunner

from os_autoinst_scripts.obs_check_package_origin import app

runner = CliRunner()


def test_check_package_origin(mocker: MockerFixture) -> None:
    mock_osc = mocker.patch("os_autoinst_scripts._common.osc")
    mock_zypper = mocker.patch("os_autoinst_scripts._common.zypper")
    mock_rpmspec = mocker.patch("os_autoinst_scripts._common.rpmspec")
    mock_grep = mocker.patch("os_autoinst_scripts._common.grep")
    mock_cut = mocker.patch("os_autoinst_scripts._common.cut")
    mock_sort = mocker.patch("os_autoinst_scripts._common.sort")
    mock_sed = mocker.patch("os_autoinst_scripts._common.sed")
    mock_tr = mocker.patch("os_autoinst_scripts._common.tr")
    mock_head = mocker.patch("os_autoinst_scripts._common.head")
    mock_basename = mocker.patch("os_autoinst_scripts._common.basename")

    mock_osc.cat.return_value = "Version: 1.0"
    mock_rpmspec.return_value = MagicMock(stdout=b"1.0\n")
    mock_zypper.return_value = MagicMock(stdout=b"Version : 1.1")
    mock_osc.se.return_value = MagicMock(stdout=b"'package'")
    mock_osc.sm.return_value = MagicMock(stdout=b"codestream")
    mock_grep.return_value = MagicMock(stdout=b"'package'")
    mock_cut.return_value = MagicMock(stdout=b"package")
    mock_sort.return_value = MagicMock(stdout=b"package")
    mock_sed.return_value = MagicMock(stdout=b"package")
    mock_tr.return_value = MagicMock(stdout=b"package")
    mock_head.return_value = MagicMock(stdout=b"package")
    mock_basename.return_value = MagicMock(stdout=b"package")

    with pathlib.Path("test.spec").open("w", encoding="utf-8") as f:
        f.write("BuildRequires: some-package")

    result = runner.invoke(app, ["some-package"])

    assert result.exit_code == 0
    assert "codestream\t1.0\t1.1" in result.stdout
