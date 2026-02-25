package main

import "testing"

func TestToSnakeCase(t *testing.T) {
	cases := []struct{ in, want string }{
		{"TailscaleIPs", "tailscale_ips"},
		{"MagicDNSSuffix", "magic_dns_suffix"},
		{"DNSName", "dns_name"},
		{"OS", "os"},
		{"TUN", "tun"},
		{"AuthURL", "auth_url"},
		{"ID", "id"},
		{"UserID", "user_id"},
		{"ExitNodeIP", "exit_node_ip"},
		{"CorpDNS", "corp_dns"},
		{"RunSSH", "run_ssh"},
		{"PeerAPIURL", "peer_api_url"},
		{"ControlURL", "control_url"},
		{"BackendState", "backend_state"},
		{"Version", "version"},
		{"SSH_HostKeys", "ssh_host_keys"},
		{"MagicDNSEnabled", "magic_dns_enabled"},
		{"WantRunning", "want_running"},
		{"DERPRegionID", "derp_region_id"},
		{"ExitNodeAllowLANAccess", "exit_node_allow_lan_access"},
		{"HTTPS", "https"},
		{"TCPForward", "tcp_forward"},
		{"IPNVersion", "ipn_version"},
		{"ProfilePicURL", "profile_pic_url"},
		{"STUNPort", "stun_port"},
		{"STUNOnly", "stun_only"},
		{"DERPPort", "derp_port"},
		{"NodeID", "node_id"},
		{"NoSNAT", "no_snat"},
		{"IsLocalIP", "is_local_ip"},
		{"IPv4", "ipv4"},
		{"IPv6", "ipv6"},
	}
	for _, c := range cases {
		got := toSnakeCase(c.in)
		if got != c.want {
			t.Errorf("toSnakeCase(%q) = %q, want %q", c.in, got, c.want)
		}
	}
}

func TestSnakeToPascal(t *testing.T) {
	cases := []struct{ in, want string }{
		{"tailscale_ips", "TailscaleIps"},
		{"dns_name", "DnsName"},
		{"backend_state", "BackendState"},
		{"version", "Version"},
		{"self_node", "SelfNode"},
	}
	for _, c := range cases {
		got := snakeToPascal(c.in)
		if got != c.want {
			t.Errorf("snakeToPascal(%q) = %q, want %q", c.in, got, c.want)
		}
	}
}
