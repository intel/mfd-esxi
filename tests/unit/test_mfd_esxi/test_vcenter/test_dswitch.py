# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT

from types import SimpleNamespace

from pyVmomi import vim


class TestDSwitch:
    def test_repr(self, dswitch):
        assert f"{dswitch}" == "DSwitch('PY-DSwitch')"

    def test_add_portgroup_duplicate_name_is_handled(self, dswitch, mocker):
        # Arrange: make the underlying vCenter API raise DuplicateName.
        dswitch.vcenter.wait_for_tasks = mocker.Mock(side_effect=vim.fault.DuplicateName())

        # Patch module logger to ensure the except-block log line is executed (line ~187).
        import mfd_esxi.vcenter.distributed_switch.dswitch as dswitch_module

        log_mock = mocker.Mock()
        mocker.patch.object(dswitch_module, "logger", log_mock)

        content = mocker.Mock()
        content.AddDVPortgroup_Task = mocker.Mock(return_value=object())
        mocker.patch.object(dswitch.__class__, "content", new_callable=mocker.PropertyMock, return_value=content)

        # Act: should not raise and should still return a DSPortgroup wrapper.
        pg = dswitch.add_portgroup(name="PG_DUP", num_ports=8)

        # Assert
        assert pg.name == "PG_DUP"
        assert pg._dswitch is dswitch
        content.AddDVPortgroup_Task.assert_called_once()

        # Assert the 'already exist' log path executed.
        assert any("already exist" in str(call.kwargs.get("msg", "")) for call in log_mock.log.mock_calls)

    def test_set_active_standby_builds_uplink_order_and_reconfigures(self, dswitch, mocker):
        # Arrange
        dswitch.vcenter.wait_for_tasks = mocker.Mock()

        # Provide a fake config spec structure that the method populates.
        spec = SimpleNamespace(defaultPortConfig=None)
        dswitch.get_ds_config_spec = mocker.Mock(return_value=spec)

        content = mocker.Mock()
        content.ReconfigureDvs_Task = mocker.Mock(return_value=object())
        mocker.patch.object(dswitch.__class__, "content", new_callable=mocker.PropertyMock, return_value=content)

        # Act
        dswitch.set_active_standby(active=["vmnic0", "vmnic1"], standby=["vmnic2"])  # lengths drive uplink names

        # Assert: uplink names use ESXI_UPLINK_FORMAT ("Uplink_%.2d")
        assert spec.defaultPortConfig.uplinkTeamingPolicy.uplinkPortOrder.activeUplinkPort == ["Uplink_01", "Uplink_02"]
        assert spec.defaultPortConfig.uplinkTeamingPolicy.uplinkPortOrder.standbyUplinkPort == ["Uplink_03"]

        content.ReconfigureDvs_Task.assert_called_once_with(spec)
        dswitch.vcenter.wait_for_tasks.assert_called_once()

    def test_uplinks_generator_returns_uplink_wrappers(self, dswitch, mocker):
        # Arrange: mock API content so uplinks are discoverable.
        uplink_names = ["Uplink_01", "Uplink_02", "Uplink_03"]
        fake_content = SimpleNamespace(
            config=SimpleNamespace(
                uplinkPortPolicy=SimpleNamespace(
                    uplinkPortName=uplink_names,
                )
            )
        )
        mocker.patch.object(dswitch.__class__, "content", new_callable=mocker.PropertyMock, return_value=fake_content)

        # Act: consume generator to execute the return line.
        uplinks = list(dswitch.uplinks)

        # Assert
        assert [u.name for u in uplinks] == uplink_names
        assert [u._number for u in uplinks] == [0, 1, 2]
        assert all(u._dswitch is dswitch for u in uplinks)
