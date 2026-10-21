#![forbid(unsafe_code)]
//! Spring NumberUtils signed integer conversion, including Java BMP digit semantics.
pub fn integer(input: &str) -> Option<i64> {
    // Spring NumberUtils removes Character.isWhitespace characters everywhere.
    let compact: String = input.chars().filter(|ch| !java_whitespace(*ch)).collect();
    let (negative, unsigned) = match compact.strip_prefix('-') {
        Some(unsigned) => (true, unsigned),
        None => (false, compact.as_str()),
    };

    // NumberUtils selects Long.decode only for these hexadecimal prefixes.
    // In particular, a leading zero alone still denotes a decimal number,
    // and a plus sign before a hexadecimal prefix is not recognized.
    let hexadecimal = unsigned
        .strip_prefix("0x")
        .or_else(|| unsigned.strip_prefix("0X"))
        .or_else(|| unsigned.strip_prefix('#'));
    let (digits, radix) = match hexadecimal {
        Some(digits) => (digits, 16),
        None => (
            unsigned
                .strip_prefix('+')
                .filter(|_| !negative)
                .unwrap_or(unsigned),
            10,
        ),
    };
    if digits.is_empty() {
        return None;
    }

    // Accumulate negatively so the signed lower boundary remains representable.
    let mut value = 0_i64;
    for ch in digits.chars() {
        let digit = java_digit(ch)?;
        if digit >= radix {
            return None;
        }
        value = value
            .checked_mul(i64::from(radix))?
            .checked_sub(i64::from(digit))?;
    }
    if negative {
        Some(value)
    } else {
        value.checked_neg()
    }
}

fn java_whitespace(ch: char) -> bool {
    matches!(ch,
        '\u{0009}'..='\u{000d}' | '\u{001c}'..='\u{0020}' |
        '\u{1680}' | '\u{2000}'..='\u{2006}' | '\u{2008}'..='\u{200a}' |
        '\u{2028}' | '\u{2029}' | '\u{205f}' | '\u{3000}'
    )
}

fn java_digit(ch: char) -> Option<u32> {
    // Long parsing uses Character.digit(char, radix), including BMP decimal
    // digits and fullwidth hex letters, but not supplementary code points.
    match ch {
        'a'..='f' => return Some(u32::from(ch) - u32::from('a') + 10),
        'A'..='F' => return Some(u32::from(ch) - u32::from('A') + 10),
        '\u{ff21}'..='\u{ff26}' => return Some(u32::from(ch) - 0xff21 + 10),
        '\u{ff41}'..='\u{ff46}' => return Some(u32::from(ch) - 0xff41 + 10),
        _ => {}
    }
    let code = u32::from(ch);
    [
        0x0030, 0x0660, 0x06f0, 0x07c0, 0x0966, 0x09e6, 0x0a66, 0x0ae6, 0x0b66, 0x0be6, 0x0c66,
        0x0ce6, 0x0d66, 0x0de6, 0x0e50, 0x0ed0, 0x0f20, 0x1040, 0x1090, 0x17e0, 0x1810, 0x1946,
        0x19d0, 0x1a80, 0x1a90, 0x1b50, 0x1bb0, 0x1c40, 0x1c50, 0xa620, 0xa8d0, 0xa900, 0xa9d0,
        0xa9f0, 0xaa50, 0xabf0, 0xff10,
    ]
    .into_iter()
    .find(|zero| (*zero..*zero + 10).contains(&code))
    .map(|zero| code - zero)
}
