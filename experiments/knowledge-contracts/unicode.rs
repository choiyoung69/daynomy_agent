#![forbid(unsafe_code)]

fn main() {
    let nbsp = "\u{a0}삼성\u{a0}";
    let emspace = "\u{2003}삼성\u{2003}";
    println!(
        "{{\"nbspTrimUtf16Length\":{},\"emSpaceTrimUtf16Length\":{}}}",
        nbsp.trim().encode_utf16().count(),
        emspace.trim().encode_utf16().count()
    );
}
