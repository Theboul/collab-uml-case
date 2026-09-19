package generator_uml.back_generator_uml.service;

import generator_uml.back_generator_uml.entity.UmlAttribute;
import generator_uml.back_generator_uml.entity.UmlClass;
import generator_uml.back_generator_uml.entity.UmlSchema;

import java.util.HashSet;
import java.util.Set;

/**
 * Única fuente de verdad de la clave primaria de cada entidad generada.
 *
 * El modelo UML no marca atributos como PK, así que "id explícito" significa un atributo
 * cuyo nombre normalizado es {@code id}. Si la clase no lo tiene, se genera un id técnico
 * sintético ({@code Long}, IDENTITY) en vez de elegir un atributo de negocio arbitrario.
 * Las subclases (herencia JOINED) usan la PK de su ancestro raíz.
 */
public final class PkResolver {

    /** synthetic = true cuando el atributo id no existe en el modelo y hay que agregarlo. */
    public record Pk(String name, String type, boolean generated, boolean synthetic) {}

    private static final Pk SYNTHETIC = new Pk("id", "Long", true, true);

    private PkResolver() {}

    public static boolean isIdName(String attributeName) {
        return "id".equals(NamingUtil.toField(attributeName));
    }

    public static Pk resolve(UmlClass c, UmlSchema schema) {
        UmlClass root = c;
        Set<String> visited = new HashSet<>();
        while (visited.add(root.getId())) {
            UmlClass parent = parentOf(root, schema);
            if (parent == null) break;
            root = parent;
        }
        return ownPk(root);
    }

    private static Pk ownPk(UmlClass c) {
        for (UmlAttribute a : c.getAttributes()) {
            if (isIdName(a.getName())) {
                // String -> PK manual; cualquier otro tipo se trata como identificador numérico autogenerado.
                boolean isString = "String".equals(TypeMapper.toJava(a.getType()));
                return isString
                        ? new Pk("id", "String", false, false)
                        : new Pk("id", "Long", true, false);
            }
        }
        return SYNTHETIC;
    }

    private static UmlClass parentOf(UmlClass c, UmlSchema schema) {
        if (schema.getRelationships() == null) return null;
        for (var rel : schema.getRelationships()) {
            if ("generalization".equals(rel.getType()) && c.getId().equals(rel.getSourceId())) {
                return schema.getClasses().stream()
                        .filter(pc -> pc.getId().equals(rel.getTargetId()))
                        .findFirst()
                        .orElse(null);
            }
        }
        return null;
    }
}
