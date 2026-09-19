package generator_uml.back_generator_uml.service;

public class TypeMapper {
    public static String toJava(String t) {
        if (t == null) return "String";
        String s = t.trim().toLowerCase();

        return switch (s) {
            case "int", "integer" -> "Integer";
            case "long" -> "Long";
            case "string" -> "String";   // 🔥 corregido
            case "bool", "boolean" -> "Boolean";
            case "float" -> "Float";
            case "double" -> "Double";
            default -> "String"; // fallback seguro
        };
    }

    /** Tipo de retorno de un método: "void" (o vacío) se conserva; el resto se mapea como cualquier tipo. */
    public static String toJavaReturn(String t) {
        if (t == null || t.isBlank() || t.trim().equalsIgnoreCase("void")) return "void";
        return toJava(t);
    }

    /**
     * Valor del "return" del stub de un método. Acepta la forma primitiva y la wrapper.
     * Long/Float necesitan sufijo: "return 0;" en un método que devuelve Long (o "0.0" en Float) no compila.
     */
    public static String defaultReturn(String javaType) {
        return switch (javaType.trim().toLowerCase()) {
            case "int", "integer", "short", "byte" -> "0";
            case "long" -> "0L";
            case "double" -> "0.0";
            case "float" -> "0.0f";
            case "boolean" -> "false";
            default -> "null";
        };
    }
}
