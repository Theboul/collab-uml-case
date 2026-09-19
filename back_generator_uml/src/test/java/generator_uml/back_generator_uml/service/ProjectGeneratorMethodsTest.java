package generator_uml.back_generator_uml.service;

import com.github.mustachejava.DefaultMustacheFactory;
import generator_uml.back_generator_uml.entity.UmlAttribute;
import generator_uml.back_generator_uml.entity.UmlClass;
import generator_uml.back_generator_uml.entity.UmlMethod;
import generator_uml.back_generator_uml.entity.UmlSchema;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.zeroturnaround.zip.ZipUtil;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.regex.Pattern;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Traducción de las operaciones UML de una clase a stubs de método en la entidad generada:
 * "void" se conserva y el "return" por defecto respeta el tipo real (wrapper) del retorno.
 */
class ProjectGeneratorMethodsTest {

    private final ProjectGenerator generator =
            new ProjectGenerator(new DefaultMustacheFactory(), new PostmanCollectionGenerator());

    private Path zip;

    @TempDir
    Path out;

    @AfterEach
    void cleanUp() throws Exception {
        if (zip != null) Files.deleteIfExists(zip);
    }

    // ---------- helpers ----------

    private static UmlMethod method(String name, String parameters, String returnType) {
        UmlMethod m = new UmlMethod();
        m.setName(name);
        m.setParameters(parameters);
        m.setReturnType(returnType);
        return m;
    }

    /** Genera un proyecto con una única clase "Producto" con los métodos dados y devuelve su Producto.java. */
    private String generateProducto(UmlMethod... methods) throws Exception {
        UmlAttribute nombre = new UmlAttribute();
        nombre.setName("nombre");
        nombre.setType("String");

        UmlClass c = new UmlClass();
        c.setId("c1");
        c.setName("Producto");
        c.setAttributes(new ArrayList<>(List.of(nombre)));
        c.setMethods(new ArrayList<>(List.of(methods)));

        UmlSchema s = new UmlSchema();
        s.setClasses(List.of(c));
        s.setRelationships(List.of());

        zip = generator.generate(s, "com.example.genapp", "methodstest-" + UUID.randomUUID());
        ZipUtil.unpack(zip.toFile(), out.toFile());
        return Files.readString(out.resolve("src/main/java/com/example/genapp/model/Producto.java"));
    }

    private static boolean matches(String source, String regex) {
        return Pattern.compile(regex).matcher(source).find();
    }

    private static String stub(String returnType, String name, String params, String returnStatement) {
        String body = returnStatement == null
                ? "\\s*// TODO: implementar\\s*"
                : "\\s*// TODO: implementar\\s*return " + Pattern.quote(returnStatement) + ";\\s*";
        return "public " + returnType + " " + name + "\\(" + params + "\\) \\{" + body + "\\}";
    }

    // ---------- void ----------

    @Test
    void voidOperation_generatesRealVoidMethodWithoutReturn() throws Exception {
        String producto = generateProducto(
                method("imprimir", "", "void"),
                method("registrar", "motivo: String", "void"));

        assertTrue(matches(producto, stub("void", "imprimir", "", null)),
                "imprimir(): void debe generar 'public void imprimir() { // TODO ... }' sin return:\n" + producto);
        assertTrue(matches(producto, stub("void", "registrar", "String motivo", null)));
        assertFalse(producto.contains("public String imprimir"), "void ya no se convierte en String");
        assertFalse(matches(producto, "void imprimir\\(\\) \\{[^}]*return"), "un método void no debe tener return");
    }

    @Test
    void operationWithoutReturnType_isTreatedAsVoid() throws Exception {
        String producto = generateProducto(
                method("vacio", "", ""),
                method("sinTipo", "", null),
                method("mayuscula", "", "Void"));

        for (String name : List.of("vacio", "sinTipo", "mayuscula")) {
            assertTrue(matches(producto, stub("void", name, "", null)), name);
        }
    }

    // ---------- return por defecto según el tipo ----------

    @Test
    void wrapperReturnTypes_getCorrectDefaultReturnInsteadOfNull() throws Exception {
        String producto = generateProducto(
                method("contar", "", "int"),
                method("calcularDescuento", "", "double"),
                method("esActivo", "", "boolean"));

        assertTrue(matches(producto, stub("Integer", "contar", "", "0")), producto);
        assertTrue(matches(producto, stub("Double", "calcularDescuento", "", "0.0")));
        assertTrue(matches(producto, stub("Boolean", "esActivo", "", "false")));
    }

    @Test
    void longAndFloatReturns_useTypedLiteralsSoTheyCompile() throws Exception {
        String producto = generateProducto(
                method("total", "", "long"),
                method("promedio", "", "float"));

        // "return 0;" en un método que devuelve Long, o "return 0.0;" en Float, no compila
        assertTrue(matches(producto, stub("Long", "total", "", "0L")));
        assertTrue(matches(producto, stub("Float", "promedio", "", "0.0f")));
    }

    @Test
    void stringAndUnknownReturnTypes_stillReturnNull() throws Exception {
        String producto = generateProducto(
                method("descripcion", "", "String"),
                method("relacionados", "", "List<Pedido>"));

        assertTrue(matches(producto, stub("String", "descripcion", "", "null")));
        assertTrue(matches(producto, stub("String", "relacionados", "", "null")),
                "los tipos no soportados siguen cayendo en el fallback String -> null");
    }

    @Test
    void parametersKeepBeingNormalizedAlongsideTheReturnType() throws Exception {
        String producto = generateProducto(method("aplicarDescuento", "porcentaje: double, cantidad: int", "double"));

        assertTrue(matches(producto, stub("Double", "aplicarDescuento", "Double porcentaje, Integer cantidad", "0.0")), producto);
    }

    // ---------- TypeMapper ----------

    @Test
    void typeMapper_defaultReturn_acceptsPrimitiveAndWrapperFormsCaseInsensitively() {
        for (String t : List.of("int", "Integer", "INTEGER")) assertEquals("0", TypeMapper.defaultReturn(t), t);
        for (String t : List.of("double", "Double")) assertEquals("0.0", TypeMapper.defaultReturn(t), t);
        for (String t : List.of("boolean", "Boolean")) assertEquals("false", TypeMapper.defaultReturn(t), t);
        for (String t : List.of("long", "Long")) assertEquals("0L", TypeMapper.defaultReturn(t), t);
        for (String t : List.of("float", "Float")) assertEquals("0.0f", TypeMapper.defaultReturn(t), t);
        for (String t : List.of("String", "Producto", "List<Pedido>")) assertEquals("null", TypeMapper.defaultReturn(t), t);
    }

    @Test
    void typeMapper_toJavaReturn_keepsVoidButLeavesToJavaUntouchedForAttributes() {
        for (String t : List.of("void", "Void", " VOID ", "", "  ")) assertEquals("void", TypeMapper.toJavaReturn(t), "[" + t + "]");
        assertEquals("void", TypeMapper.toJavaReturn(null));
        assertEquals("Double", TypeMapper.toJavaReturn("double"));
        assertEquals("String", TypeMapper.toJavaReturn("Producto"));
        // toJava (atributos/parámetros) no cambia: "void" no es un tipo válido de campo
        assertEquals("String", TypeMapper.toJava("void"));
    }
}
