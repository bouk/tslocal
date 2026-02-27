package main

import (
	"fmt"
	"os"
	"path/filepath"
	"reflect"

	"tailscale.com/client/tailscale/apitype"
	"tailscale.com/ipn"
	"tailscale.com/ipn/ipnstate"
	"tailscale.com/tailcfg"
	"tailscale.com/types/dnstype"
)

// typeEntry pairs a reflect.Type with the Go type name for registration.
type typeEntry struct {
	Name string
	Type reflect.Type
}

func main() {
	// Determine project root (two levels up from cmd/typegen)
	exe, err := os.Getwd()
	if err != nil {
		fmt.Fprintf(os.Stderr, "error getting working directory: %v\n", err)
		os.Exit(1)
	}
	projectRoot := filepath.Join(exe, "..", "..")
	tailscaleDir := filepath.Join(projectRoot, "tailscale")

	// Source files to parse for comments (only files containing reachable types)
	sourceFiles := []string{
		"ipn/ipnstate/ipnstate.go",
		"tailcfg/tailcfg.go",
		"ipn/serve.go",
		"client/tailscale/apitype/apitype.go",
		"types/dnstype/dnstype.go",
	}

	// Register all type names first so we know which nested types to generate
	types := []typeEntry{
		// ipnstate
		{"Status", reflect.TypeOf(ipnstate.Status{})},
		{"PeerStatus", reflect.TypeOf(ipnstate.PeerStatus{})},
		{"TailnetStatus", reflect.TypeOf(ipnstate.TailnetStatus{})},
		{"ExitNodeStatus", reflect.TypeOf(ipnstate.ExitNodeStatus{})},
		{"PingResult", reflect.TypeOf(ipnstate.PingResult{})},
		{"NetworkLockStatus", reflect.TypeOf(ipnstate.NetworkLockStatus{})},
		{"TKAKey", reflect.TypeOf(ipnstate.TKAKey{})},
		{"TKAPeer", reflect.TypeOf(ipnstate.TKAPeer{})},
		{"PeerStatusLite", reflect.TypeOf(ipnstate.PeerStatusLite{})},

		// tailcfg
		{"UserProfile", reflect.TypeOf(tailcfg.UserProfile{})},
		{"Node", reflect.TypeOf(tailcfg.Node{})},
		{"Hostinfo", reflect.TypeOf(tailcfg.Hostinfo{})},
		{"NetInfo", reflect.TypeOf(tailcfg.NetInfo{})},
		{"Service", reflect.TypeOf(tailcfg.Service{})},
		{"Location", reflect.TypeOf(tailcfg.Location{})},
		{"TPMInfo", reflect.TypeOf(tailcfg.TPMInfo{})},
		{"ClientVersion", reflect.TypeOf(tailcfg.ClientVersion{})},
		{"DERPMap", reflect.TypeOf(tailcfg.DERPMap{})},
		{"DERPRegion", reflect.TypeOf(tailcfg.DERPRegion{})},
		{"DERPNode", reflect.TypeOf(tailcfg.DERPNode{})},
		{"DERPHomeParams", reflect.TypeOf(tailcfg.DERPHomeParams{})},
		{"VIPService", reflect.TypeOf(tailcfg.VIPService{})},
		{"PortRange", reflect.TypeOf(tailcfg.PortRange{})},
		{"ProtoPortRange", reflect.TypeOf(tailcfg.ProtoPortRange{})},

		// ipn
		{"Prefs", reflect.TypeOf(ipn.Prefs{})},
		{"MaskedPrefs", reflect.TypeOf(ipn.MaskedPrefs{})},
		{"AutoUpdatePrefs", reflect.TypeOf(ipn.AutoUpdatePrefs{})},
		{"AppConnectorPrefs", reflect.TypeOf(ipn.AppConnectorPrefs{})},
		{"Notify", reflect.TypeOf(ipn.Notify{})},
		{"PartialFile", reflect.TypeOf(ipn.PartialFile{})},
		{"OutgoingFile", reflect.TypeOf(ipn.OutgoingFile{})},
		{"EngineStatus", reflect.TypeOf(ipn.EngineStatus{})},
		{"ServeConfig", reflect.TypeOf(ipn.ServeConfig{})},
		{"TCPPortHandler", reflect.TypeOf(ipn.TCPPortHandler{})},
		{"WebServerConfig", reflect.TypeOf(ipn.WebServerConfig{})},
		{"HTTPHandler", reflect.TypeOf(ipn.HTTPHandler{})},
		{"ServiceConfig", reflect.TypeOf(ipn.ServiceConfig{})},
		{"LoginProfile", reflect.TypeOf(ipn.LoginProfile{})},
		{"NetworkProfile", reflect.TypeOf(ipn.NetworkProfile{})},
		{"AutoUpdatePrefsMask", reflect.TypeOf(ipn.AutoUpdatePrefsMask{})},

		// apitype
		{"WhoIsResponse", reflect.TypeOf(apitype.WhoIsResponse{})},
		{"WaitingFile", reflect.TypeOf(apitype.WaitingFile{})},
		{"FileTarget", reflect.TypeOf(apitype.FileTarget{})},
		{"ExitNodeSuggestionResponse", reflect.TypeOf(apitype.ExitNodeSuggestionResponse{})},
		{"ReloadConfigResponse", reflect.TypeOf(apitype.ReloadConfigResponse{})},
		{"DNSOSConfig", reflect.TypeOf(apitype.DNSOSConfig{})},
		{"DNSQueryResponse", reflect.TypeOf(apitype.DNSQueryResponse{})},
		{"OptionalFeatures", reflect.TypeOf(apitype.OptionalFeatures{})},
		{"SetPushDeviceTokenRequest", reflect.TypeOf(apitype.SetPushDeviceTokenRequest{})},

		// dnstype
		{"Resolver", reflect.TypeOf(dnstype.Resolver{})},
	}

	// Build candidates map and pre-populate registeredTypeNames
	// (needed for View type resolution during the reachability walk)
	candidates := map[string]reflect.Type{}
	for _, te := range types {
		candidates[te.Name] = te.Type
		registeredTypeNames[te.Name] = true
	}

	// Walk from root types to find all reachable structs
	rootTypes := []reflect.Type{
		reflect.TypeOf(ipnstate.Status{}),
		reflect.TypeOf(apitype.WhoIsResponse{}),
		reflect.TypeOf(ipn.ServeConfig{}),
	}
	reachable := collectReachable(rootTypes, candidates)

	// Filter types to only reachable ones
	var filteredTypes []typeEntry
	for _, te := range types {
		if reachable[te.Name] {
			filteredTypes = append(filteredTypes, te)
		}
	}
	types = filteredTypes

	// Re-set registeredTypeNames to only reachable types
	registeredTypeNames = map[string]bool{}
	for _, te := range types {
		registeredTypeNames[te.Name] = true
	}

	// Parse comments from Go source files
	comments, err := parseComments(tailscaleDir, sourceFiles)
	if err != nil {
		fmt.Fprintf(os.Stderr, "error parsing comments: %v\n", err)
		os.Exit(1)
	}

	// Inspect all structs
	var structInfos []*StructInfo
	for _, te := range types {
		si := inspectStruct(te.Type, comments)
		structInfos = append(structInfos, si)
	}

	// Generate Rust
	rustCode := generateRust(structInfos)
	rustPath := filepath.Join(projectRoot, "rust", "src", "types.rs")
	if err := os.WriteFile(rustPath, []byte(rustCode), 0644); err != nil {
		fmt.Fprintf(os.Stderr, "error writing %s: %v\n", rustPath, err)
		os.Exit(1)
	}
	fmt.Printf("Generated %s\n", rustPath)

	// Generate Python
	pythonCode := generatePython(structInfos)
	pythonPath := filepath.Join(projectRoot, "python", "src", "tslocalapi", "_generated_types.py")
	if err := os.WriteFile(pythonPath, []byte(pythonCode), 0644); err != nil {
		fmt.Fprintf(os.Stderr, "error writing %s: %v\n", pythonPath, err)
		os.Exit(1)
	}
	fmt.Printf("Generated %s\n", pythonPath)

	// Generate TypeScript
	tsCode := generateTypeScript(structInfos)
	tsPath := filepath.Join(projectRoot, "ts", "src", "types.ts")
	if err := os.WriteFile(tsPath, []byte(tsCode), 0644); err != nil {
		fmt.Fprintf(os.Stderr, "error writing %s: %v\n", tsPath, err)
		os.Exit(1)
	}
	fmt.Printf("Generated %s\n", tsPath)
}
