import React from "react";
import {
  Pressable,
  Text,
  TextInput,
  View,
  StyleSheet,
  type TextInputProps,
} from "react-native";
import { theme as c } from "./theme";
export function Button({
  title,
  onPress,
  secondary = false,
  disabled = false,
  danger = false,
}: {
  title: string;
  onPress: () => void;
  secondary?: boolean;
  disabled?: boolean;
  danger?: boolean;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled }}
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => [
        s.button,
        secondary && s.secondary,
        danger && { backgroundColor: c.danger },
        disabled && { opacity: 0.4 },
        pressed && { opacity: 0.7 },
      ]}
    >
      <Text style={[s.buttonText, secondary && { color: c.accent }]}>
        {title}
      </Text>
    </Pressable>
  );
}
export function Field({ label, ...props }: TextInputProps & { label: string }) {
  return (
    <View style={{ gap: 7 }}>
      <Text style={s.label}>{label}</Text>
      <TextInput
        accessibilityLabel={label}
        placeholderTextColor={c.muted}
        {...props}
        style={[
          s.input,
          props.multiline && { minHeight: 112, textAlignVertical: "top" },
          props.style,
        ]}
      />
    </View>
  );
}
export function Section({
  title,
  detail,
  children,
}: {
  title: string;
  detail?: string;
  children: React.ReactNode;
}) {
  return (
    <View style={s.section}>
      <View style={{ gap: 6 }}>
        <Text accessibilityRole="header" style={s.heading}>
          {title}
        </Text>
        {!!detail && <Text style={s.muted}>{detail}</Text>}
      </View>
      {children}
    </View>
  );
}
export function Empty({ title, detail }: { title: string; detail: string }) {
  return (
    <View style={s.empty}>
      <Text style={s.emptyTitle}>{title}</Text>
      <Text style={[s.muted, { textAlign: "center" }]}>{detail}</Text>
    </View>
  );
}
export function Chip({
  title,
  selected,
  onPress,
}: {
  title: string;
  selected: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityState={{ selected }}
      style={({ pressed }) => [
        s.chip,
        selected && { backgroundColor: c.ink, borderColor: c.ink },
        pressed && { opacity: 0.7 },
      ]}
    >
      <Text style={{ fontWeight: "600", color: selected ? "#FFF" : c.muted }}>
        {title}
      </Text>
    </Pressable>
  );
}
export const s = StyleSheet.create({
  button: {
    minHeight: 48,
    borderRadius: 12,
    backgroundColor: c.accent,
    paddingHorizontal: 20,
    paddingVertical: 14,
    justifyContent: "center",
    alignItems: "center",
  },
  secondary: { backgroundColor: c.soft },
  buttonText: { color: "#FFF", fontWeight: "700", fontSize: 15 },
  input: {
    minHeight: 50,
    borderWidth: 1,
    borderColor: c.line,
    borderRadius: 12,
    padding: 14,
    backgroundColor: c.surface,
    color: c.ink,
    fontSize: 16,
  },
  label: { fontSize: 13, fontWeight: "600", color: c.muted },
  heading: {
    fontSize: 20,
    fontWeight: "700",
    letterSpacing: -0.5,
    color: c.ink,
  },
  muted: { fontSize: 14, lineHeight: 21, color: c.muted },
  section: {
    padding: 20,
    backgroundColor: c.surface,
    borderRadius: 18,
    gap: 18,
  },
  empty: {
    paddingVertical: 32,
    paddingHorizontal: 20,
    alignItems: "center",
    gap: 10,
  },
  emptyTitle: { fontSize: 17, fontWeight: "600", color: c.ink },
  chip: {
    minHeight: 44,
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderRadius: 24,
    borderWidth: 1,
    borderColor: c.line,
    justifyContent: "center",
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12,
  },
  title: { fontSize: 17, fontWeight: "700", color: c.ink },
  divider: { height: 1, backgroundColor: c.line },
  caption: { fontSize: 12, color: c.muted },
  badge: {
    fontSize: 11,
    color: c.accent,
    fontWeight: "700",
    letterSpacing: 0.7,
  },
  body: { fontSize: 16, lineHeight: 26, color: c.ink },
});
