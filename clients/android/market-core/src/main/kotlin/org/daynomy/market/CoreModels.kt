package org.daynomy.market

interface SessionTransport : HttpTransport {
    suspend fun request(method: String, path: String, jsonBody: String? = null): String
}
data class AccountProfile(val id: Long, val email: String, val name: String?, val nickname: String, val role: String)
