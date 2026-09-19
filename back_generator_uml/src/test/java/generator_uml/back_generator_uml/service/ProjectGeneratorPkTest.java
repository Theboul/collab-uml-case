package generator_uml.back_generator_uml.service;

import com.github.mustachejava.DefaultMustacheFactory;
import generator_uml.back_generator_uml.entity.UmlAttribute;
import generator_uml.back_generator_uml.entity.UmlClass;
import generator_uml.back_generator_uml.entity.UmlRelationship;
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
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Regla de PK del generador: un atributo "id" explícito se respeta (con su tipo real); si la clase
 * no lo tiene se genera un id técnico Long/IDENTITY en vez de tomar un atributo de negocio arbitrario.
 */
class ProjectGeneratorPkTest {

    private static final String PKG = "com/example/genapp";

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

    private static UmlClass clazz(String id, String name, String... nameTypePairs) {
        UmlClass c = new UmlClass();
        c.setId(id);
        c.setName(name);
        List<UmlAttribute> attrs = new ArrayList<>();
        for (int i = 0; i < nameTypePairs.length; i += 2) {
            UmlAttribute a = new UmlAttribute();
            a.setName(nameTypePairs[i]);
            a.setType(nameTypePairs[i + 1]);
            attrs.add(a);
        }
        c.setAttributes(attrs);
        c.setMethods(new ArrayList<>());
        return c;
    }

    private static UmlRelationship rel(String type, String source, String target, String... labels) {
        UmlRelationship r = new UmlRelationship();
        r.setId("rel-" + source + "-" + target);
        r.setType(type);
        r.setSourceId(source);
        r.setTargetId(target);
        r.setLabels(List.of(labels));
        return r;
    }

    private static UmlSchema schema(List<UmlClass> classes, List<UmlRelationship> rels) {
        UmlSchema s = new UmlSchema();
        s.setClasses(classes);
        s.setRelationships(rels);
        return s;
    }

    private Path generate(UmlSchema schema) throws Exception {
        String artifactId = "pktest-" + UUID.randomUUID();
        zip = generator.generate(schema, "com.example.genapp", artifactId);
        ZipUtil.unpack(zip.toFile(), out.toFile());
        return out;
    }

    private String read(String relative) throws Exception {
        return Files.readString(out.resolve("src/main/java/" + PKG + "/" + relative));
    }

    private static int count(String text, String regex) {
        Matcher m = Pattern.compile(regex).matcher(text);
        int n = 0;
        while (m.find()) n++;
        return n;
    }

    // ---------- tests ----------

    @Test
    void classWithoutExplicitId_getsSyntheticLongIdInsteadOfFirstAttribute() throws Exception {
        UmlSchema s = schema(
                List.of(clazz("c1", "Producto", "nombre", "String", "precio", "Double"),
                        clazz("c2", "Pedido", "fecha", "String")),
                List.of(rel("association", "c1", "c2", "*", "*")));
        generate(s);

        for (String entity : List.of("Producto", "Pedido")) {
            String model = read("model/" + entity + ".java");
            assertTrue(Pattern.compile("@Id\\s+@GeneratedValue\\(strategy = GenerationType\\.IDENTITY\\)\\s+private Long id;")
                    .matcher(model).find(), entity + " debe tener id Long IDENTITY sintético");
            assertEquals(1, count(model, "@Id\\b"), entity + " debe tener exactamente un @Id");
            assertEquals(1, count(model, "private \\w+ id;"), entity + " no debe duplicar el campo id");
            assertTrue(read("repository/" + entity + "Repository.java").contains("JpaRepository<" + entity + ", Long>"));
        }
        // el atributo de negocio deja de ser PK pero se conserva como columna
        String producto = read("model/Producto.java");
        assertTrue(producto.contains("private String nombre;"));
        assertFalse(Pattern.compile("@Id\\s+(@GeneratedValue[^\\n]*\\s+)?private String nombre").matcher(producto).find());
        assertTrue(producto.contains("private Double precio;"));
    }

    @Test
    void manyToManyIntermediateService_findsEntitiesByLongId() throws Exception {
        UmlSchema s = schema(
                List.of(clazz("c1", "Producto", "nombre", "String"), clazz("c2", "Pedido", "fecha", "String")),
                List.of(rel("association", "c1", "c2", "*", "*")));
        generate(s);

        String svc = read("service/PedidoProductoService.java");
        assertTrue(svc.contains("Optional<Pedido> findPedidoById(Long id)"));
        assertTrue(svc.contains("Optional<Producto> findProductoById(Long id)"));
        // ambos repositorios que usa el servicio intermedio deben aceptar Long
        assertTrue(read("repository/PedidoRepository.java").contains("JpaRepository<Pedido, Long>"));
        assertTrue(read("repository/ProductoRepository.java").contains("JpaRepository<Producto, Long>"));
        assertTrue(read("repository/PedidoProductoRepository.java").contains("JpaRepository<PedidoProducto, Long>"));
    }

    @Test
    void explicitLongId_isKeptAndNotDuplicated_evenWhenNotFirstAttribute() throws Exception {
        UmlSchema s = schema(
                List.of(clazz("c1", "Producto", "id", "Long", "nombre", "String"),
                        clazz("c2", "Pedido", "fecha", "String", "id", "Integer")),
                List.of());
        generate(s);

        String producto = read("model/Producto.java");
        assertTrue(Pattern.compile("@Id\\s+@GeneratedValue\\(strategy = GenerationType\\.IDENTITY\\)\\s+private Long id;")
                .matcher(producto).find());
        assertEquals(1, count(producto, "private \\w+ id;"), "el id explícito no debe duplicarse con uno sintético");
        assertTrue(producto.contains("private String nombre;"));

        // id explícito Integer, en segunda posición: sigue siendo la PK (numérica -> Long autogenerada)
        String pedido = read("model/Pedido.java");
        assertTrue(Pattern.compile("@Id\\s+@GeneratedValue\\(strategy = GenerationType\\.IDENTITY\\)\\s+private Long id;")
                .matcher(pedido).find());
        assertEquals(1, count(pedido, "private \\w+ id;"));
        assertFalse(Pattern.compile("@Id\\s+(@GeneratedValue[^\\n]*\\s+)?private String fecha").matcher(pedido).find());
    }

    @Test
    void explicitStringId_keepsRealTypeWithoutGeneratedValue() throws Exception {
        UmlSchema s = schema(List.of(clazz("c1", "Cliente", "id", "String", "nombre", "String")), List.of());
        generate(s);

        String model = read("model/Cliente.java");
        assertTrue(Pattern.compile("@Id\\s+private String id;").matcher(model).find());
        assertFalse(model.contains("GeneratedValue"));
        assertEquals(1, count(model, "private \\w+ id;"));
        assertTrue(read("repository/ClienteRepository.java").contains("JpaRepository<Cliente, String>"));
    }

    @Test
    void childOfParentWithoutId_inheritsParentSyntheticLongId() throws Exception {
        UmlSchema s = schema(
                List.of(clazz("p", "Persona", "nombre", "String"), clazz("e", "Empleado", "salario", "Double")),
                List.of(rel("generalization", "e", "p", "1", "1")));
        generate(s);

        assertTrue(read("model/Persona.java").contains("private Long id;"));
        String empleado = read("model/Empleado.java");
        assertTrue(empleado.contains("extends Persona"));
        assertEquals(0, count(empleado, "private \\w+ id;"), "la subclase hereda el id, no lo redeclara");
        assertTrue(read("repository/EmpleadoRepository.java").contains("JpaRepository<Empleado, Long>"));
    }

    @Test
    void postmanCollection_usesSameLongIdAsGeneratedCode() throws Exception {
        UmlSchema s = schema(
                List.of(clazz("c1", "Producto", "nombre", "String"), clazz("c2", "Pedido", "fecha", "String")),
                List.of(rel("association", "c1", "c2", "*", "*")));
        generate(s);

        String collection = Files.readString(out.resolve(zip.getFileName().toString().replace(".zip", "") + "-postman-collection.json"));
        assertFalse(collection.contains("example-id"), "el id ya no es String: los ejemplos no deben usar example-id");
        assertTrue(collection.contains("/api/producto/1"));
        assertTrue(collection.contains("nombre"), "nombre es un atributo normal y debe aparecer en el body de ejemplo");
    }

    // ---------- servicio/controller: tipo real de la PK del destino ----------

    @Test
    void manyToMany_withExplicitStringPkOnOneSide_intermediateServiceUsesRealPkType() throws Exception {
        UmlSchema s = schema(
                List.of(clazz("c1", "Producto", "id", "String", "nombre", "String"),
                        clazz("c2", "Pedido", "fecha", "String")),
                List.of(rel("association", "c1", "c2", "*", "*")));
        generate(s);

        assertTrue(read("repository/ProductoRepository.java").contains("JpaRepository<Producto, String>"));
        assertTrue(read("repository/PedidoRepository.java").contains("JpaRepository<Pedido, Long>"));

        String svc = read("service/PedidoProductoService.java");
        assertTrue(svc.contains("Optional<Producto> findProductoById(String id)"), "PK String explícita -> firma String");
        assertTrue(svc.contains("Optional<Pedido> findPedidoById(Long id)"), "PK sintética -> firma Long");
        assertFalse(svc.contains("findProductoById(Long"), "no debe quedar el Long fijo");

        String ctrl = read("controller/PedidoProductoController.java");
        assertTrue(ctrl.contains("String relId = convertToString(value);"));
        assertTrue(ctrl.contains("Long relId = convertToLong(value);"));
        assertTrue(ctrl.contains("service.findProductoById(relId)"));
    }

    @Test
    void regularRelationsToStringPkTarget_serviceAndControllerUseRealPkType() throws Exception {
        UmlSchema s = schema(
                List.of(clazz("ped", "Pedido", "fecha", "String"),
                        clazz("cli", "Cliente", "id", "String", "nombre", "String"),
                        clazz("usu", "Usuario", "nombre", "String"),
                        clazz("per", "Perfil", "id", "String", "bio", "String"),
                        clazz("com", "Compra", "monto", "Double"),
                        clazz("prv", "Proveedor", "id", "String", "razon", "String")),
                List.of(rel("association", "ped", "cli", "*", "1"),   // Pedido ManyToOne Cliente (lado source)
                        rel("association", "usu", "per", "1", "1"),   // Usuario OneToOne Perfil
                        rel("association", "prv", "com", "1", "*"))); // Compra ManyToOne Proveedor (lado target)
        generate(s);

        assertTrue(read("service/PedidoService.java").contains("Optional<Cliente> findClienteById(String id)"));
        assertTrue(read("service/UsuarioService.java").contains("Optional<Perfil> findPerfilById(String id)"));
        assertTrue(read("service/CompraService.java").contains("Optional<Proveedor> findProveedorById(String id)"));

        assertTrue(read("controller/PedidoController.java").contains("String relId = convertToString(value);"));
        assertTrue(read("controller/UsuarioController.java").contains("String relId = convertToString(value);"));
        assertTrue(read("controller/CompraController.java").contains("String relId = convertToString(value);"));
        assertFalse(read("controller/PedidoController.java").contains("Long relId"));
    }

    // ---------- herencia de varios niveles ----------

    private static UmlSchema threeLevelChain(UmlClass root) {
        UmlClass middle = clazz("mid", "Mamifero", "patas", "Integer");
        UmlClass leaf = clazz("leaf", "Perro", "raza", "String");
        return schema(List.of(leaf, middle, root),
                List.of(rel("generalization", "leaf", "mid", "1", "1"),
                        rel("generalization", "mid", root.getId(), "1", "1")));
    }

    @Test
    void pkResolver_threeLevelChainWithoutId_resolvesSameSyntheticPkFromRoot() {
        UmlClass root = clazz("root", "Animal", "nombre", "String");
        UmlSchema s = threeLevelChain(root);

        PkResolver.Pk expected = new PkResolver.Pk("id", "Long", true, true);
        for (UmlClass c : s.getClasses()) {
            assertEquals(expected, PkResolver.resolve(c, s), c.getName());
        }
    }

    @Test
    void threeLevelChainWithoutId_generatesTechnicalIdOnlyOnceInTheRoot() throws Exception {
        generate(threeLevelChain(clazz("root", "Animal", "nombre", "String")));

        String animal = read("model/Animal.java");
        String mamifero = read("model/Mamifero.java");
        String perro = read("model/Perro.java");

        assertTrue(mamifero.contains("extends Animal"));
        assertTrue(perro.contains("extends Mamifero"));

        assertTrue(Pattern.compile("@Id\\s+@GeneratedValue\\(strategy = GenerationType\\.IDENTITY\\)\\s+private Long id;")
                .matcher(animal).find(), "la raíz declara el id técnico");
        assertEquals(1, count(animal, "private \\w+ id;"));
        assertEquals(0, count(mamifero, "private \\w+ id;"), "el nivel intermedio no debe duplicar el id");
        assertEquals(0, count(perro, "private \\w+ id;"), "la hoja no debe duplicar el id");
        assertEquals(1, count(animal, "@Id\\b") + count(mamifero, "@Id\\b") + count(perro, "@Id\\b"),
                "exactamente un @Id en toda la cadena");

        for (String entity : List.of("Animal", "Mamifero", "Perro")) {
            assertTrue(read("repository/" + entity + "Repository.java").contains("JpaRepository<" + entity + ", Long>"), entity);
            assertTrue(read("service/" + entity + "Service.java").contains("findById(Long id)"), entity);
        }
    }

    @Test
    void threeLevelChainWithExplicitStringIdInRoot_allLevelsInheritStringPk() throws Exception {
        UmlSchema s = threeLevelChain(clazz("root", "Animal", "id", "String", "nombre", "String"));

        for (UmlClass c : s.getClasses()) {
            PkResolver.Pk pk = PkResolver.resolve(c, s);
            assertEquals("String", pk.type(), c.getName());
            assertFalse(pk.synthetic(), c.getName());
        }

        generate(s);
        assertEquals(1, count(read("model/Animal.java"), "private String id;"));
        assertEquals(0, count(read("model/Mamifero.java"), "private \\w+ id;"));
        assertEquals(0, count(read("model/Perro.java"), "private \\w+ id;"));
        for (String entity : List.of("Animal", "Mamifero", "Perro")) {
            assertTrue(read("repository/" + entity + "Repository.java").contains("JpaRepository<" + entity + ", String>"), entity);
        }
    }
}
