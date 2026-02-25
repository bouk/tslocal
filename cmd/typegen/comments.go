package main

import (
	"go/ast"
	"go/parser"
	"go/token"
	"path/filepath"
	"strings"
)

// StructComments holds doc comments for a struct and its fields.
type StructComments struct {
	Doc    string            // struct-level doc comment
	Fields map[string]string // fieldName -> doc comment
}

// parseComments parses Go source files and extracts doc comments for structs and fields.
func parseComments(tailscaleDir string, files []string) (map[string]*StructComments, error) {
	result := make(map[string]*StructComments)

	for _, file := range files {
		path := filepath.Join(tailscaleDir, file)
		fset := token.NewFileSet()
		f, err := parser.ParseFile(fset, path, nil, parser.ParseComments)
		if err != nil {
			return nil, err
		}

		for _, decl := range f.Decls {
			genDecl, ok := decl.(*ast.GenDecl)
			if !ok || genDecl.Tok != token.TYPE {
				continue
			}

			for _, spec := range genDecl.Specs {
				typeSpec, ok := spec.(*ast.TypeSpec)
				if !ok {
					continue
				}

				structType, ok := typeSpec.Type.(*ast.StructType)
				if !ok {
					continue
				}

				sc := &StructComments{
					Fields: make(map[string]string),
				}

				// Get struct-level doc comment
				if typeSpec.Doc != nil {
					sc.Doc = cleanComment(typeSpec.Doc.Text())
				} else if genDecl.Doc != nil && len(genDecl.Specs) == 1 {
					sc.Doc = cleanComment(genDecl.Doc.Text())
				}

				// Get field-level comments
				for _, field := range structType.Fields.List {
					if len(field.Names) == 0 {
						// Embedded field - use the type name
						continue
					}
					for _, name := range field.Names {
						var comment string
						if field.Doc != nil {
							comment = cleanComment(field.Doc.Text())
						} else if field.Comment != nil {
							comment = cleanComment(field.Comment.Text())
						}
						if comment != "" {
							sc.Fields[name.Name] = comment
						}
					}
				}

				result[typeSpec.Name.Name] = sc
			}
		}
	}

	return result, nil
}

// cleanComment strips leading/trailing whitespace and trims trailing newlines.
func cleanComment(s string) string {
	s = strings.TrimSpace(s)
	// Remove trailing period-newline patterns
	lines := strings.Split(s, "\n")
	var cleaned []string
	for _, line := range lines {
		cleaned = append(cleaned, strings.TrimRight(line, " "))
	}
	return strings.Join(cleaned, "\n")
}
