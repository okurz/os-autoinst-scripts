# Copyright SUSE LLC

from pytest_mock import MockerFixture
from typer.testing import CliRunner

from os_autoinst_scripts import obs_check_package_origin

runner = CliRunner()


def test_get_package_version(mocker: MockerFixture) -> None:
    mocker.patch(
        "os_autoinst_scripts.obs_check_package_origin.get_package_version",
        return_value="1.0",
    )
    version = obs_check_package_origin.get_package_version("some-package")
    assert version == "1.0"
