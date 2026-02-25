package main

import (
	"fmt"
	"strings"
)

// zodPrimitive maps a base TypeScript type to its Zod schema expression.
// parentName is the name of the struct being generated; self-references use the
// forward-declared lazy ref variable.
func zodPrimitive(tsType, parentName string) string {
	switch tsType {
	case "string":
		return "z.string()"
	case "boolean":
		return "z.boolean()"
	case "number":
		return "z.number()"
	case "bigint":
		return "int64"
	case "unknown":
		return "z.unknown()"
	default:
		// Reference to another generated struct schema
		if tsType == parentName {
			return fmt.Sprintf("_%sRef", tsType)
		}
		return tsType + "Schema"
	}
}

// zodFieldExpr returns the complete Zod expression for a struct field.
// parentName is the name of the struct being generated.
func zodFieldExpr(fi FieldInfo, parentName string) string {
	isOmit := fi.Omit == "omitempty" || fi.Omit == "omitzero"

	// Collections: goSlice/goMap already handle null/undefined → default via .nullish().
	// No need for .optional() — the output type is always T[]/Record (never undefined).
	if fi.IsSlice {
		elemTS := strings.TrimSuffix(fi.TypeScriptType, "[]")
		elemZod := zodPrimitive(elemTS, parentName)
		return fmt.Sprintf("goSlice(%s)", elemZod)
	}

	if fi.IsMap {
		valZod := zodMapValue(fi.TypeScriptType, parentName)
		return fmt.Sprintf("goMap(%s)", valZod)
	}

	// Non-collection field: strip optionality markers from TypeScriptType
	baseTS := fi.TypeScriptType
	baseTS = strings.TrimSuffix(baseTS, " | undefined")
	baseTS = strings.TrimSuffix(baseTS, " | null")
	expr := zodPrimitive(baseTS, parentName)

	if fi.IsOptional || isOmit {
		// Go nil pointers serialize as JSON null (not absent), so use .nullish()
		// to accept both null and undefined.
		expr += ".nullish()"
	} else if fi.IsNestedStruct {
		// Non-optional nested struct: Go always serializes with zero-value fields,
		// but absent in partial data → default to empty object (inner fields have their own defaults).
		expr += ".default({})"
	} else {
		// Non-optional, non-omit primitive: add zero-value default matching
		// Go's json.Unmarshal behavior for absent fields.
		switch baseTS {
		case "string":
			expr += `.default("")`
		case "number":
			expr += ".default(0)"
		case "bigint":
			expr += ".default(0)"
		case "boolean":
			expr += ".default(false)"
		}
	}
	return expr
}

// zodMapValue extracts the Zod expression for the value type of a Record<K, V>.
// parentName is the name of the struct being generated.
func zodMapValue(tsType, parentName string) string {
	// Parse "Record<K, V>" or "Record<K, V | null>"
	idx := strings.Index(tsType, ", ")
	if idx == -1 {
		return "z.unknown()"
	}
	valPart := tsType[idx+2 : len(tsType)-1] // strip trailing ">"

	// Map-of-slices case: "V[] | null"
	valPart = strings.TrimSuffix(valPart, " | null")
	if strings.HasSuffix(valPart, "[]") {
		elemType := strings.TrimSuffix(valPart, "[]")
		return fmt.Sprintf("goSlice(%s)", zodPrimitive(elemType, parentName))
	}

	return zodPrimitive(valPart, parentName)
}

// topologicalSort reorders structs so that dependencies come before dependents.
// This is required because Zod runtime values cannot forward-reference.
func topologicalSort(structs []*StructInfo) []*StructInfo {
	structNames := map[string]bool{}
	byName := map[string]*StructInfo{}
	for _, si := range structs {
		structNames[si.Name] = true
		byName[si.Name] = si
	}

	// Build dependency graph
	deps := map[string][]string{}
	for _, si := range structs {
		deps[si.Name] = extractStructDeps(si, structNames)
	}

	// DFS post-order traversal
	visited := map[string]bool{}
	var order []*StructInfo

	var visit func(name string)
	visit = func(name string) {
		if visited[name] {
			return
		}
		visited[name] = true
		for _, dep := range deps[name] {
			visit(dep)
		}
		if si, ok := byName[name]; ok {
			order = append(order, si)
		}
	}

	for _, si := range structs {
		visit(si.Name)
	}
	return order
}

// extractStructDeps returns the names of generated structs that a struct depends on.
func extractStructDeps(si *StructInfo, structNames map[string]bool) []string {
	seen := map[string]bool{}
	var deps []string

	add := func(name string) {
		if structNames[name] && name != si.Name && !seen[name] {
			seen[name] = true
			deps = append(deps, name)
		}
	}

	for _, fi := range si.Fields {
		if fi.IsNestedStruct && fi.NestedTypeName != "" {
			add(fi.NestedTypeName)
			continue
		}

		if fi.IsSlice {
			elem := strings.TrimSuffix(fi.TypeScriptType, "[]")
			add(elem)
			continue
		}

		if fi.IsMap {
			idx := strings.Index(fi.TypeScriptType, ", ")
			if idx != -1 {
				val := fi.TypeScriptType[idx+2 : len(fi.TypeScriptType)-1]
				val = strings.TrimSuffix(val, " | null")
				val = strings.TrimSuffix(val, "[]")
				add(val)
			}
			continue
		}
	}

	return deps
}

// hasSelfReference returns true if any field in the struct references the struct itself.
func hasSelfReference(si *StructInfo) bool {
	for _, fi := range si.Fields {
		if fi.IsNestedStruct && fi.NestedTypeName == si.Name {
			return true
		}
		// Check map values and slice elements for self-references
		tsType := fi.TypeScriptType
		if fi.IsMap {
			idx := strings.Index(tsType, ", ")
			if idx != -1 {
				val := tsType[idx+2 : len(tsType)-1]
				val = strings.TrimSuffix(val, " | null")
				val = strings.TrimSuffix(val, "[]")
				if val == si.Name {
					return true
				}
			}
		}
		if fi.IsSlice {
			elem := strings.TrimSuffix(tsType, "[]")
			if elem == si.Name {
				return true
			}
		}
	}
	return false
}

func generateTypeScript(structs []*StructInfo) string {
	var b strings.Builder

	// Header
	b.WriteString("// Code generated by cmd/typegen; DO NOT EDIT.\n\n")
	b.WriteString("import { z } from \"zod\";\n\n")

	// Helper functions for Go nil-slice/nil-map → default transforms.
	// .nullish() accepts both null (Go nil) and undefined (absent field).
	b.WriteString("const goSlice = <T extends z.ZodTypeAny>(item: T) =>\n")
	b.WriteString("  z.array(item).nullish().transform(v => v ?? []);\n\n")
	b.WriteString("const goMap = <V extends z.ZodTypeAny>(val: V) =>\n")
	b.WriteString("  z.record(z.string(), val).nullish().transform(v => v ?? {});\n\n")
	b.WriteString("const int64 = z.union([z.number().int(), z.bigint()]).transform(v => BigInt(v));\n")

	// Sort structs in dependency order (leaf types first)
	sorted := topologicalSort(structs)

	for _, si := range sorted {
		b.WriteString("\n")

		// Check if this struct has self-references (e.g. ServeConfig.Foreground → ServeConfig)
		selfRef := hasSelfReference(si)
		if selfRef {
			// Emit a forward-declared lazy reference to break the circular type inference
			b.WriteString(fmt.Sprintf("const _%sRef: z.ZodTypeAny = z.lazy(() => %sSchema);\n", si.Name, si.Name))
		}

		// Struct doc comment
		if si.Comment != "" {
			writeComment(&b, si.Comment, "")
		}

		b.WriteString(fmt.Sprintf("export const %sSchema = z.object({\n", si.Name))

		for _, fi := range si.Fields {
			// Field doc comment
			if fi.Comment != "" {
				writeComment(&b, fi.Comment, "  ")
			}

			zodExpr := zodFieldExpr(fi, si.Name)
			b.WriteString(fmt.Sprintf("  %s: %s,\n", fi.JSONName, zodExpr))
		}

		b.WriteString("});\n")
		b.WriteString(fmt.Sprintf("export type %s = z.infer<typeof %sSchema>;\n", si.Name, si.Name))
	}

	// Append client-specific types as Zod schemas
	b.WriteString(`
/** Alias for TailnetStatus for backward compatibility. */
export const CurrentTailnetSchema = z.object({
  Name: z.string(),
  MagicDNSSuffix: z.string(),
  MagicDNSEnabled: z.boolean(),
});
export type CurrentTailnet = z.infer<typeof CurrentTailnetSchema>;

/** Profile status containing current and all profiles. */
export const ProfileStatusSchema = z.object({
  CurrentProfile: LoginProfileSchema,
  AllProfiles: z.array(LoginProfileSchema),
});
export type ProfileStatus = z.infer<typeof ProfileStatusSchema>;

/** Bitmask for IPN bus watch notifications. */
export enum NotifyWatchOpt {
  /** Receive initial state at start of watch. */
  NotifyInitialState = 1 << 1,
  /** Receive full network map updates. */
  NotifyInitialNetMap = 1 << 2,
  /** Receive partial state updates. */
  NotifyInitialDriveShares = 1 << 3,
  /** Receive full prefs in initial state. */
  NotifyInitialPrefs = 1 << 4,
  /** Receive outgoing file updates. */
  NotifyInitialOutgoingFiles = 1 << 5,
}
`)

	return b.String()
}

// writeComment writes a JSDoc comment block.
func writeComment(b *strings.Builder, comment, indent string) {
	lines := strings.Split(comment, "\n")
	if len(lines) == 1 {
		b.WriteString(fmt.Sprintf("%s/** %s */\n", indent, lines[0]))
	} else {
		b.WriteString(fmt.Sprintf("%s/**\n", indent))
		for _, line := range lines {
			b.WriteString(fmt.Sprintf("%s * %s\n", indent, line))
		}
		b.WriteString(fmt.Sprintf("%s */\n", indent))
	}
}
