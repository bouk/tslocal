package main

import (
	"encoding/json"
	"fmt"
	"net/netip"
	"reflect"
	"strings"
	"time"

	"tailscale.com/tailcfg"
	"tailscale.com/tka"
	"tailscale.com/types/key"
	"tailscale.com/types/opt"
)

// FieldInfo describes a single struct field for code generation.
type FieldInfo struct {
	GoName   string // Go field name
	JSONName string // wire name from json tag
	Omit     string // "omitempty", "omitzero", or ""
	GoType   reflect.Type

	// Resolved target language types
	RustType       string
	PythonType     string
	TypeScriptType string

	// Whether this is an optional (pointer/Option) field
	IsOptional bool

	// Whether this is a slice/array that should default to empty (not null)
	IsSlice bool

	// Whether this is a map
	IsMap bool

	// Whether this is a nested struct that we generate
	IsNestedStruct bool
	NestedTypeName string

	// Whether this is a flattened/embedded struct
	IsEmbedded bool

	// Whether this field is skipped during serialization (json:"-")
	IsSkipped bool

	// Comment from Go source
	Comment string
}

// StructInfo describes a struct for code generation.
type StructInfo struct {
	Name    string
	Fields  []FieldInfo
	Comment string
}

// knownTypes maps Go reflect.Type to (rust, python, typescript) type strings.
// Types here are "terminal" - they don't need further recursion.
var knownTypeMap = map[reflect.Type][3]string{
	reflect.TypeOf(""):                          {"String", "str", "string"},
	reflect.TypeOf(false):                       {"bool", "bool", "boolean"},
	reflect.TypeOf(int(0)):                      {"i64", "int", "bigint"},
	reflect.TypeOf(int32(0)):                    {"i32", "int", "number"},
	reflect.TypeOf(int64(0)):                    {"i64", "int", "bigint"},
	reflect.TypeOf(uint(0)):                     {"u64", "int", "bigint"},
	reflect.TypeOf(uint16(0)):                   {"u16", "int", "number"},
	reflect.TypeOf(uint64(0)):                   {"u64", "int", "bigint"},
	reflect.TypeOf(float64(0)):                  {"f64", "float", "number"},
	reflect.TypeOf(time.Time{}):                 {"String", "str", "string"},
	reflect.TypeOf(time.Duration(0)):            {"i64", "int", "bigint"},
	reflect.TypeOf(netip.Addr{}):                {"String", "str", "string"},
	reflect.TypeOf(netip.Prefix{}):              {"String", "str", "string"},
	reflect.TypeOf(netip.AddrPort{}):            {"String", "str", "string"},
	reflect.TypeOf(opt.Bool("")):                {"Option<bool>", "bool | None", "boolean | undefined"},
	reflect.TypeOf(key.NodePublic{}):            {"String", "str", "string"},
	reflect.TypeOf(key.MachinePublic{}):         {"String", "str", "string"},
	reflect.TypeOf(key.DiscoPublic{}):           {"String", "str", "string"},
	reflect.TypeOf(key.NLPublic{}):              {"String", "str", "string"},
	reflect.TypeOf(tailcfg.StableNodeID("")):    {"String", "str", "string"},
	reflect.TypeOf(tailcfg.NodeID(0)):           {"i64", "int", "bigint"},
	reflect.TypeOf(tailcfg.UserID(0)):           {"i64", "int", "bigint"},
	reflect.TypeOf(tailcfg.NodeCapability("")):  {"String", "str", "string"},
	reflect.TypeOf(tailcfg.PeerCapability("")):  {"String", "str", "string"},
	reflect.TypeOf(tailcfg.ServiceProto("")):    {"String", "str", "string"},
	reflect.TypeOf(tailcfg.ServiceName("")):     {"String", "str", "string"},
	reflect.TypeOf(tailcfg.CapabilityVersion(0)): {"i64", "int", "bigint"},
	reflect.TypeOf(json.RawMessage{}):           {"serde_json::Value", "Any", "unknown"},
	reflect.TypeOf(tailcfg.RawMessage("")):      {"serde_json::Value", "Any", "unknown"},
	reflect.TypeOf(tka.NodeKeySignature{}):      {"serde_json::Value", "Any", "unknown"},
}

// resolveType resolves a Go type to target language type strings.
// It returns (rust, python, typescript, isOptional, isSlice, isMap, isNestedStruct, nestedName).
func resolveType(t reflect.Type) (rust, python, ts string, isOptional, isSlice, isMap, isNestedStruct bool, nestedName string) {
	// Check known types first
	if mapped, ok := knownTypeMap[t]; ok {
		rustType := mapped[0]
		isOpt := strings.HasPrefix(rustType, "Option<")
		return rustType, mapped[1], mapped[2], isOpt, false, false, false, ""
	}

	// Handle pointer types
	if t.Kind() == reflect.Ptr {
		innerRust, innerPy, innerTS, _, innerSlice, innerMap, innerNested, innerNestedName := resolveType(t.Elem())
		// If the inner type is already Option<...>, don't double-wrap
		if strings.HasPrefix(innerRust, "Option<") {
			return innerRust, innerPy, innerTS, true, innerSlice, innerMap, innerNested, innerNestedName
		}
		return fmt.Sprintf("Option<%s>", innerRust), fmt.Sprintf("%s | None", innerPy), fmt.Sprintf("%s | undefined", innerTS),
			true, innerSlice, innerMap, innerNested, innerNestedName
	}

	// Handle slice types
	if t.Kind() == reflect.Slice {
		// Special case: []byte
		if t.Elem().Kind() == reflect.Uint8 {
			return "String", "str", "string", false, false, false, false, ""
		}
		// For slice elements, strip pointers - []*T becomes Vec<T> not Vec<Option<Box<T>>>
		elemType := t.Elem()
		if elemType.Kind() == reflect.Ptr {
			elemType = elemType.Elem()
		}
		innerRust, innerPy, innerTS, _, _, _, _, _ := resolveType(elemType)
		return fmt.Sprintf("Vec<%s>", innerRust), fmt.Sprintf("list[%s]", innerPy), fmt.Sprintf("%s[]", innerTS),
			false, true, false, false, ""
	}

	// Handle array types (e.g. [32]byte)
	if t.Kind() == reflect.Array {
		if t.Elem().Kind() == reflect.Uint8 {
			return "String", "str", "string", false, false, false, false, ""
		}
		innerRust, innerPy, innerTS, _, _, _, _, _ := resolveType(t.Elem())
		return fmt.Sprintf("Vec<%s>", innerRust), fmt.Sprintf("list[%s]", innerPy), fmt.Sprintf("%s[]", innerTS),
			false, true, false, false, ""
	}

	// Handle map types
	if t.Kind() == reflect.Map {
		keyRust, keyPy, keyTS, _, _, _, _, _ := resolveType(t.Key())
		// For map values, strip the pointer - map values in Go JSON are never null,
		// they're just omitted from the map if not present
		valType := t.Elem()
		if valType.Kind() == reflect.Ptr {
			valType = valType.Elem()
		}
		valRust, valPy, valTS, _, valIsSlice, _, _, _ := resolveType(valType)
		// JSON map keys are always strings; Python msgspec needs str keys
		pyKey := keyPy
		if pyKey != "str" {
			pyKey = "str"
		}
		// In Go, map values that are slices can be nil (serialized as null).
		// Wrap slice values in Option to handle this.
		if valIsSlice {
			return fmt.Sprintf("HashMap<%s, Option<%s>>", keyRust, valRust),
				fmt.Sprintf("dict[%s, %s | None]", pyKey, valPy),
				fmt.Sprintf("Record<%s, %s | null>", keyTS, valTS),
				false, false, true, false, ""
		}
		return fmt.Sprintf("HashMap<%s, %s>", keyRust, valRust),
			fmt.Sprintf("dict[%s, %s]", pyKey, valPy),
			fmt.Sprintf("Record<%s, %s>", keyTS, valTS),
			false, false, true, false, ""
	}

	// Handle views.Slice[T] (pointer to it)
	if t.Kind() == reflect.Struct && strings.Contains(t.Name(), "SliceView") {
		// This is typically views.SliceView[T, V] - treat as a JSON array
		return "serde_json::Value", "Any", "unknown", false, true, false, false, ""
	}

	// Handle known view types (e.g. HostinfoView, LocationView)
	if strings.HasSuffix(t.Name(), "View") && t.Kind() == reflect.Struct {
		// Try to find the underlying type name
		baseName := strings.TrimSuffix(t.Name(), "View")
		// Check if we have this as a known generated struct
		if isRegisteredType(baseName) {
			return baseName, baseName, baseName, false, false, false, true, baseName
		}
		// For views we can't resolve, use the base type as opaque
		return "serde_json::Value", "Any", "unknown", false, false, false, false, ""
	}

	// Handle struct types - check if it's one we generate
	if t.Kind() == reflect.Struct {
		name := t.Name()
		if name != "" && isRegisteredType(name) {
			return name, name, name, false, false, false, true, name
		}
		// Unknown struct - treat as opaque JSON
		return "serde_json::Value", "Any", "unknown", false, false, false, false, ""
	}

	// Handle named types that are based on primitive types (string aliases etc.)
	switch t.Kind() {
	case reflect.String:
		return "String", "str", "string", false, false, false, false, ""
	case reflect.Int, reflect.Int64:
		return "i64", "int", "bigint", false, false, false, false, ""
	case reflect.Int32:
		return "i32", "int", "number", false, false, false, false, ""
	case reflect.Uint16:
		return "u16", "int", "number", false, false, false, false, ""
	case reflect.Uint64, reflect.Uint:
		return "u64", "int", "bigint", false, false, false, false, ""
	case reflect.Bool:
		return "bool", "bool", "boolean", false, false, false, false, ""
	case reflect.Float64:
		return "f64", "float", "number", false, false, false, false, ""
	}

	// Fallback: opaque JSON value
	return "serde_json::Value", "Any", "unknown", false, false, false, false, ""
}

// registeredTypeNames is the set of type names we plan to generate.
var registeredTypeNames = map[string]bool{}

func isRegisteredType(name string) bool {
	return registeredTypeNames[name]
}


// inspectStruct inspects a Go struct type and returns FieldInfo for each field.
func inspectStruct(t reflect.Type, comments map[string]*StructComments) *StructInfo {
	if t.Kind() == reflect.Ptr {
		t = t.Elem()
	}

	name := t.Name()
	si := &StructInfo{
		Name: name,
	}

	if sc, ok := comments[name]; ok {
		si.Comment = sc.Doc
	}

	for i := 0; i < t.NumField(); i++ {
		f := t.Field(i)

		// Skip unexported fields
		if !f.IsExported() {
			continue
		}

		// Skip fields of type structs.Incomparable (marker type)
		if f.Type.Name() == "Incomparable" {
			continue
		}

		// Handle embedded structs (like MaskedPrefs embedding Prefs)
		// Include the embedded struct's fields inline
		if f.Anonymous {
			embeddedType := f.Type
			if embeddedType.Kind() == reflect.Ptr {
				embeddedType = embeddedType.Elem()
			}
			if embeddedType.Kind() == reflect.Struct {
				embSi := inspectStruct(embeddedType, comments)
				si.Fields = append(si.Fields, embSi.Fields...)
			}
			continue
		}

		fi := FieldInfo{
			GoName: f.Name,
			GoType: f.Type,
		}

		// Parse json tag
		jsonTag := f.Tag.Get("json")
		fi.JSONName, fi.Omit = parseJSONTag(jsonTag, f.Name)

		// Fields with json:"-" are included but marked as skipped
		if fi.JSONName == "-" {
			fi.IsSkipped = true
			fi.JSONName = f.Name
		}

		// Resolve types
		fi.RustType, fi.PythonType, fi.TypeScriptType, fi.IsOptional, fi.IsSlice, fi.IsMap, fi.IsNestedStruct, fi.NestedTypeName = resolveType(f.Type)

		// Handle views.Slice[T] which is a pointer to a views.Slice
		if isViewsSlice(f.Type) {
			elemType := getViewsSliceElem(f.Type)
			if elemType != nil {
				innerRust, innerPy, innerTS, _, _, _, _, _ := resolveType(elemType)
				fi.RustType = fmt.Sprintf("Vec<%s>", innerRust)
				fi.PythonType = fmt.Sprintf("list[%s]", innerPy)
				fi.TypeScriptType = fmt.Sprintf("%s[]", innerTS)
				fi.IsSlice = true
				fi.IsOptional = true // *views.Slice is like a nullable slice
			}
		}

		// Get comment
		if sc, ok := comments[name]; ok {
			if c, ok := sc.Fields[f.Name]; ok {
				fi.Comment = c
			}
		}

		si.Fields = append(si.Fields, fi)
	}

	return si
}

func isViewsSlice(t reflect.Type) bool {
	if t.Kind() == reflect.Ptr {
		t = t.Elem()
	}
	return t.Kind() == reflect.Struct && strings.HasPrefix(t.Name(), "Slice[")
}

func getViewsSliceElem(t reflect.Type) reflect.Type {
	if t.Kind() == reflect.Ptr {
		t = t.Elem()
	}
	// views.Slice has a method "At" that returns the element type
	atMethod, ok := t.MethodByName("At")
	if ok && atMethod.Type.NumOut() == 1 {
		return atMethod.Type.Out(0)
	}
	// Try the pointer receiver
	pt := reflect.PointerTo(t)
	atMethod, ok = pt.MethodByName("At")
	if ok && atMethod.Type.NumOut() == 1 {
		return atMethod.Type.Out(0)
	}
	return nil
}

// parseJSONTag parses a json struct tag and returns the wire name and omit behavior.
func parseJSONTag(tag, fieldName string) (name string, omit string) {
	if tag == "" {
		return fieldName, ""
	}
	if tag == "-" {
		return "-", ""
	}

	parts := strings.Split(tag, ",")
	name = parts[0]
	if name == "" {
		name = fieldName
	}

	for _, p := range parts[1:] {
		if p == "omitempty" || p == "omitzero" {
			omit = p
		}
	}

	return name, omit
}

// collectReachable performs a recursive walk from the given root types,
// following pointers, slices, maps, View types, embedded structs, and
// views.Slice[T] to find all struct types reachable from the roots.
// Only types present in the candidates map are collected.
func collectReachable(roots []reflect.Type, candidates map[string]reflect.Type) map[string]bool {
	reachable := map[string]bool{}
	visited := map[reflect.Type]bool{}

	var walk func(t reflect.Type)
	walk = func(t reflect.Type) {
		if visited[t] {
			return
		}
		visited[t] = true

		// Terminal types don't need further recursion
		if _, ok := knownTypeMap[t]; ok {
			return
		}

		// Pointer: unwrap
		if t.Kind() == reflect.Ptr {
			walk(t.Elem())
			return
		}

		// Slice: follow element (strip pointer like resolveType does)
		if t.Kind() == reflect.Slice {
			if t.Elem().Kind() == reflect.Uint8 {
				return // []byte is terminal
			}
			elem := t.Elem()
			if elem.Kind() == reflect.Ptr {
				elem = elem.Elem()
			}
			walk(elem)
			return
		}

		// Array: follow element
		if t.Kind() == reflect.Array {
			walk(t.Elem())
			return
		}

		// Map: follow key and value (strip pointer on value like resolveType)
		if t.Kind() == reflect.Map {
			walk(t.Key())
			val := t.Elem()
			if val.Kind() == reflect.Ptr {
				val = val.Elem()
			}
			walk(val)
			return
		}

		// views.Slice[T]: get element via At method
		if t.Kind() == reflect.Struct && strings.HasPrefix(t.Name(), "Slice[") {
			atMethod, ok := t.MethodByName("At")
			if ok && atMethod.Type.NumOut() == 1 {
				walk(atMethod.Type.Out(0))
			}
			pt := reflect.PointerTo(t)
			atMethod, ok = pt.MethodByName("At")
			if ok && atMethod.Type.NumOut() == 1 {
				walk(atMethod.Type.Out(0))
			}
			return
		}

		// View types (e.g. HostinfoView → Hostinfo)
		if strings.HasSuffix(t.Name(), "View") && t.Kind() == reflect.Struct {
			baseName := strings.TrimSuffix(t.Name(), "View")
			if cand, ok := candidates[baseName]; ok {
				walk(cand)
			}
			return
		}

		// Struct types: if it's a candidate, mark reachable and walk fields
		if t.Kind() == reflect.Struct {
			name := t.Name()
			if name == "" {
				return
			}
			if _, ok := candidates[name]; !ok {
				return
			}
			reachable[name] = true
			for i := 0; i < t.NumField(); i++ {
				f := t.Field(i)
				if !f.IsExported() {
					continue
				}
				if f.Type.Name() == "Incomparable" {
					continue
				}
				walk(f.Type)
			}
			return
		}
	}

	for _, root := range roots {
		walk(root)
	}
	return reachable
}
