public class UnicodeProbe {
    public static void main(String[] args) {
        String nbsp = "\u00a0삼성\u00a0";
        String emspace = "\u2003삼성\u2003";
        System.out.printf("{\"nbspStripUtf16Length\":%d,\"emSpaceStripUtf16Length\":%d}%n",
                nbsp.strip().length(), emspace.strip().length());
    }
}
