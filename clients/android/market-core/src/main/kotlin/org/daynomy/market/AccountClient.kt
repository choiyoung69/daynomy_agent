package org.daynomy.market

import java.math.BigDecimal
import kotlinx.serialization.json.*

class AccountClient(private val transport: SessionTransport) {
    suspend fun me(): AccountProfile = profile(transport.get("/api/users/me"))
    suspend fun updateNickname(nickname: String): AccountProfile = profile(transport.request("PATCH", "/api/users/me",
        buildJsonObject { put("nickname", nickname) }.toString()))
    suspend fun logout() {
        try { transport.request("POST", "/api/auth/logout") }
        finally { (transport as? SessionHttpTransport)?.clearSession() }
    }
    suspend fun delete() {
        try { transport.request("DELETE", "/api/users/me") }
        finally { (transport as? SessionHttpTransport)?.clearSession() }
    }
    private fun profile(raw: String): AccountProfile {
        val row = coreObject(raw)
        val name = row["name"]
        val role = coreText(row["role"])
        if (role !in setOf("USER", "ADMIN")) invalidCore()
        return AccountProfile(coreId(row["id"]), coreText(row["email"]),
            if (name == null || name == JsonNull) null else coreText(name),
            coreText(row["nickname"]), role)
    }
}
internal fun invalidCore(): Nothing = throw ResponseFormatException("서버 응답 형식이 올바르지 않습니다.")
internal fun coreElement(raw: String): JsonElement = try { Json.parseToJsonElement(raw) } catch (_: IllegalArgumentException) { invalidCore() }
internal fun coreObject(raw: String): JsonObject = coreElement(raw) as? JsonObject ?: invalidCore()
internal fun coreText(value: JsonElement?): String = (value as? JsonPrimitive)?.takeIf { it.isString }?.content ?: invalidCore()
internal fun coreDecimal(value: JsonElement?): BigDecimal {
    val primitive = value as? JsonPrimitive ?: invalidCore()
    if (primitive.isString || primitive == JsonNull) invalidCore()
    return primitive.content.toBigDecimalOrNull() ?: invalidCore()
}
internal fun coreId(value: JsonElement?): Long {
    val id = try { coreDecimal(value).longValueExact() } catch (_: ArithmeticException) { invalidCore() }
    if (id !in 1..9_007_199_254_740_991L) invalidCore()
    return id
}
internal fun checkedCoreId(value: Long): Long {
    require(value in 1..9_007_199_254_740_991L) { "잘못된 식별자입니다." }
    return value
}
