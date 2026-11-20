import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import ts from "typescript";
import { expect, it } from "vitest";

function sourceFiles(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    return entry.isDirectory()
      ? sourceFiles(path)
      : path.endsWith(".tsx") && !path.endsWith(".test.tsx")
        ? [path]
        : [];
  });
}

it("keeps visible JSX text and accessibility labels in the translation dictionary", () => {
  const violations: string[] = [];
  const visibleAttributes = new Set([
    "title",
    "description",
    "placeholder",
    "alt",
    "aria-label",
    "label",
  ]);
  for (const path of sourceFiles(join(process.cwd(), "src"))) {
    const source = ts.createSourceFile(
      path,
      readFileSync(path, "utf8"),
      ts.ScriptTarget.Latest,
      true,
      ts.ScriptKind.TSX,
    );
    function check(node: ts.Node) {
      const literalText = ts.isJsxText(node) && node.text.trim();
      const literalAttribute =
        ts.isJsxAttribute(node) &&
        visibleAttributes.has(node.name.getText(source)) &&
        node.initializer &&
        ts.isStringLiteral(node.initializer) &&
        node.initializer.text.trim();
      const literalExpression =
        ts.isJsxExpression(node) &&
        node.expression &&
        (ts.isStringLiteral(node.expression) ||
          ts.isNoSubstitutionTemplateLiteral(node.expression)) &&
        node.expression.text.trim();
      if (literalText || literalAttribute || literalExpression) {
        const { line } = source.getLineAndCharacterOfPosition(node.getStart(source));
        violations.push(`${path}:${line + 1}: ${node.getText(source)}`);
      }
      ts.forEachChild(node, check);
    }
    check(source);
  }
  expect(violations).toEqual([]);
});
