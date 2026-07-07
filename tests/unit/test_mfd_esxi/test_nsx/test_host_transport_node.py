# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: MIT
import pytest

from mfd_esxi.exceptions import NsxResourceSetupError
from mfd_esxi.nsx.connection import NsxConnection
from mfd_esxi.nsx.host_transport_node import NsxHostTransportNode


class TestHostTransportNode:
    @pytest.fixture
    def connection(self, mocker):
        connection = mocker.create_autospec(NsxConnection)
        yield connection
        mocker.stopall()

    @pytest.fixture
    def host_transport_node(self, connection, mocker):
        host_tn = NsxHostTransportNode(name="test_transport_node", connection=connection)
        host_tn._patch = mocker.Mock()

        yield host_tn
        mocker.stopall()

    def test_require_discovered_node_raises_when_absent(self, host_transport_node, mocker):
        mock_fdn = mocker.patch(
            "mfd_esxi.nsx.host_transport_node.NsxFabricDiscoveredNode",
        )
        mock_fdn.return_value.content = None

        with pytest.raises(NsxResourceSetupError, match="test_transport_node"):
            host_transport_node._require_discovered_node()

    def test_require_discovered_node_returns_node(self, host_transport_node, mocker):
        mock_node = mocker.Mock(external_id="ext-999")
        mock_fdn = mocker.patch(
            "mfd_esxi.nsx.host_transport_node.NsxFabricDiscoveredNode",
        )
        mock_fdn.return_value.content = mock_node

        result = host_transport_node._require_discovered_node()

        assert result is mock_node

    def test_add_already_exists_returns_early(self, host_transport_node, mocker):
        host_transport_node._get_content = mocker.Mock(return_value=mocker.Mock())

        host_transport_node.add()

        host_transport_node._patch.assert_not_called()

    def test_add_no_discovery_raises(self, host_transport_node, mocker):
        host_transport_node._get_content = mocker.Mock(return_value=None)
        host_transport_node._require_discovered_node = mocker.Mock(
            side_effect=NsxResourceSetupError("not found"),
        )

        with pytest.raises(NsxResourceSetupError):
            host_transport_node.add()

    def test_add_host_visible_no_patch(self, host_transport_node, mocker):
        host_transport_node._get_content = mocker.Mock(return_value=None)
        host_transport_node._require_discovered_node = mocker.Mock(
            return_value=mocker.Mock(external_id="ext-123"),
        )

        host_transport_node.add()

        host_transport_node._patch.assert_not_called()

    def test_add_switch_with_uplink_param(self, host_transport_node, mocker):
        vds_id = "test"
        mock_standard_host_switch = mocker.patch(
            "mfd_esxi.nsx.host_transport_node.StandardHostSwitch",
            autospec=True,
        )
        host_transport_node.add_switch(
            host_switch_name="test_sw",
            uplink_name="uplink",
            transport_zone_name="test_tz",
            vds_id=vds_id,
            uplinks=4,
            ip_pool_id="IPV6pool",
        )
        mock_standard_host_switch.assert_called_once()
        args, kwargs = mock_standard_host_switch.call_args
        assert kwargs["host_switch_name"] == "test_sw"
        assert len(kwargs["uplinks"]) == 4

    def test_add_switch_without_uplink_param(self, host_transport_node, mocker):
        # test whether Exception is not raised when uplink param is not provided
        mock_standard_host_switch = mocker.patch(
            "mfd_esxi.nsx.host_transport_node.StandardHostSwitch",
            autospec=True,
        )
        host_transport_node.add_switch(
            host_switch_name="test_sw",
            uplink_name="uplink",
            transport_zone_name="test_tz",
            vds_id="test",
            ip_pool_id="IPV4pool",
        )
        mock_standard_host_switch.assert_called_once()
        args, kwargs = mock_standard_host_switch.call_args
        from mfd_esxi.const import ESXI_UPLINK_NUMBER

        assert len(kwargs["uplinks"]) == ESXI_UPLINK_NUMBER

    def test_add_switch_no_payload_no_discovery_raises(self, host_transport_node, mocker):
        host_transport_node._get_content = mocker.Mock(return_value=None)
        host_transport_node._require_discovered_node = mocker.Mock(
            side_effect=NsxResourceSetupError("not found"),
        )

        with pytest.raises(NsxResourceSetupError):
            host_transport_node.add_switch(
                host_switch_name="test_sw",
                uplink_name="uplink",
                transport_zone_name="test_tz",
                vds_id="test",
                ip_pool_id=None,
            )

    def test_add_switch_no_payload_creates_node_inline(self, host_transport_node, mocker):
        host_transport_node._get_content = mocker.Mock(return_value=None)
        host_transport_node._require_discovered_node = mocker.Mock(
            return_value=mocker.Mock(external_id="ext-456"),
        )
        mocker.patch(
            "mfd_esxi.nsx.host_transport_node.StandardHostSwitch",
            autospec=True,
        )

        host_transport_node.add_switch(
            host_switch_name="test_sw",
            uplink_name="uplink",
            transport_zone_name="test_tz",
            vds_id="test",
            ip_pool_id=None,
        )

        host_transport_node._patch.assert_called_once()

    def test_get_uplink_profile_names_no_payload_returns_empty(self, host_transport_node, mocker):
        host_transport_node._get_content = mocker.Mock(return_value=None)

        result = host_transport_node.get_uplink_profile_names()

        assert result == []
        host_transport_node._patch.assert_not_called()

    def test_get_uplink_profile_names_no_host_switch_spec_returns_empty(self, host_transport_node, mocker):
        mock_payload = mocker.Mock()
        mock_payload.host_switch_spec = None
        host_transport_node._get_content = mocker.Mock(return_value=mock_payload)

        result = host_transport_node.get_uplink_profile_names()

        assert result == []
        host_transport_node._patch.assert_not_called()

    def test_get_uplink_profile_names_returns_names_without_patch(self, host_transport_node, mocker):
        from mfd_esxi.nsx.host_transport_node import HostSwitchProfileTypeIdEntry

        uplink_entry = mocker.Mock()
        uplink_entry.key = HostSwitchProfileTypeIdEntry.KEY_UPLINKHOSTSWITCHPROFILE
        uplink_entry.value = "/infra/host-switch-profiles/my-uplink-profile"

        mock_switch = mocker.Mock()
        mock_switch.host_switch_profile_ids = [uplink_entry]

        mock_spec = mocker.Mock()
        mock_spec.host_switches = [mock_switch]

        mock_payload = mocker.Mock()
        mock_payload.host_switch_spec.convert_to.return_value = mock_spec
        host_transport_node._get_content = mocker.Mock(return_value=mock_payload)

        result = host_transport_node.get_uplink_profile_names()

        assert result == ["my-uplink-profile"]
        host_transport_node._patch.assert_not_called()
