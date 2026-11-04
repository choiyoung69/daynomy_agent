package org.daynomy.market

import java.io.IOException
import java.math.BigDecimal
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.test.runTest
import org.junit.Assert.*
import org.junit.Test

class PortfolioAiContractTest {
    @Test fun savedReadAndExplicitGenerationUseMemberEndpointsWithoutBody() = runTest {
        val transport = AiTestTransport(); val client = PortfolioAnalysisClient(transport)
        client.saved(); client.generate(); client.generate(true)
        transport.reply = "[]"; assertTrue(client.history().isEmpty())
        assertEquals(listOf(
            AiTestCall("GET", "/api/users/me/portfolio/analysis", null),
            AiTestCall("POST", "/api/users/me/portfolio/analysis", null),
            AiTestCall("POST", "/api/users/me/portfolio/analysis/refresh", null),
            AiTestCall("GET", "/api/users/me/portfolio/analysis/history", null)
        ), transport.calls)
    }

    @Test fun partialAnalysisKeepsNullsAndExactDecimalsAndSourceEvidence() = runTest {
        val result = PortfolioAnalysisClient(AiTestTransport()).saved()
        assertEquals(7L, result.analysisId)
        val analysis = requireNotNull(result.analysis)
        assertNull(analysis.overallDirection); assertNull(analysis.overallScore)
        assertNull(analysis.analyzedAt)
        assertEquals(BigDecimal("33.12345678901234567890"), analysis.analyzedWeight)
        val impact = analysis.impacts.single()
        assertNull(impact.direction); assertNull(impact.impactLevel)
        assertEquals(BigDecimal("33.12345678901234567890"), impact.weight)
        assertEquals("https://example.org/evidence", impact.sources.single().url)
        assertEquals("원문 인용", impact.sources.single().factQuote)
    }

    @Test fun missingRequiredNullFieldsWrongTypesEnumsAndUnsafeSourcesFailWholeResponse() = runTest {
        val invalid = mutableListOf("null", "[]", "{}", "broken")
        for (field in listOf("\"lastCheckOutcome\":null", "\"lastFailedAt\":null", "\"failureCode\":null", "\"changeReason\":null")) {
            invalid += AI_TEST_SAVED.replace("$field,", "")
        }
        invalid += AI_TEST_SAVED.replace("\"READY\"", "\"UNKNOWN\"")
        invalid += AI_TEST_SAVED.replace("\"matchesCurrentPortfolio\":true", "\"matchesCurrentPortfolio\":\"true\"")
        invalid += AI_TEST_SAVED.replace("\"analysisId\":7", "\"analysisId\":7.5")
        invalid += AI_TEST_SAVED.replace("\"totalAssetCount\":2", "\"totalAssetCount\":2.5")
        invalid += AI_TEST_SAVED.replace("\"overallScore\":null", "\"overallScore\":\"0\"")
        invalid += AI_TEST_SAVED.replace("\"direction\":null", "\"direction\":\"POSITIVE\"")
        invalid += AI_TEST_SAVED.replace("https://example.org/evidence", "javascript:alert(1)")
        invalid += AI_TEST_SAVED.replace("\"excerpt\":\"근거\"", "\"excerpt\":null")
        for (body in invalid) expectFailure<ResponseFormatException> { PortfolioAnalysisClient(AiTestTransport(body)).saved() }
    }

    @Test fun emptySavedResultAndHistoryOrderNullablePreviousIdArePreserved() = runTest {
        val empty = AI_TEST_SAVED.substringBefore("\"analysis\":") + "\"analysis\":null}"
        assertNull(PortfolioAnalysisClient(AiTestTransport(empty)).saved().analysis)
        val historyRow = """{"analysisId":7,"previousAnalysisId":null,"analyzedAt":"2026-11-04T00:00:00Z","changeReason":"생성","analysis":$AI_TEST_ANALYSIS}"""
        val transport = AiTestTransport("[$historyRow,${historyRow.replace("\"analysisId\":7", "\"analysisId\":3")}]")
        val history = PortfolioAnalysisClient(transport).history()
        assertEquals(listOf(7L, 3L), history.map { it.analysisId }); assertNull(history.first().previousAnalysisId)
        for (body in listOf("null", "{}", "[$historyRow,{}]", "[$historyRow,null]")) {
            transport.reply = body
            expectFailure<ResponseFormatException> { PortfolioAnalysisClient(transport).history() }
        }
    }

    @Test fun apiIoAndCancellationFailuresKeepIdentityAndAreNeverRetried() = runTest {
        for (failure in listOf(IOException("lost"), ApiException(409, "PROCESSING", "private"), CancellationException("cancel"))) {
            val transport = AiTestTransport().apply { answer = { throw failure } }
            assertSame(failure, expectFailure<Exception> { PortfolioAnalysisClient(transport).generate() })
            assertEquals(1, transport.calls.size)
        }
    }
}

internal data class AiTestCall(val method: String, val path: String, val body: String?)
internal class AiTestTransport(var reply: String = AI_TEST_SAVED) : SessionTransport {
    val calls = mutableListOf<AiTestCall>()
    var answer: suspend (AiTestCall) -> String = { reply }
    override suspend fun get(pathAndQuery: String) = request("GET", pathAndQuery)
    override suspend fun request(method: String, path: String, jsonBody: String?): String {
        val call = AiTestCall(method, path, jsonBody); calls += call; return answer(call)
    }
}
internal const val AI_TEST_SOURCE = """{"title":"근거","url":"https://example.org/evidence","publishedOn":null,"occurredOn":null,"excerpt":"근거","factQuote":"원문 인용"}"""
internal const val AI_TEST_ANALYSIS = """{"coverage":"PARTIAL","analyzedWeight":33.12345678901234567890,"totalAssetCount":2,"analyzedAssetCount":1,"overallDirection":null,"overallScore":null,"positiveImpactScore":1.25,"negativeImpactScore":2.50,"analyzedAt":null,"overallImpact":"부분 분석","impacts":[{"assetName":"종목","weight":33.12345678901234567890,"direction":null,"impactLevel":null,"issueSummary":"요약","expectedReaction":"반응","outlook":"전망","reason":"이유","evidenceSentence":"근거","sources":[$AI_TEST_SOURCE],"rank":1}],"sources":[$AI_TEST_SOURCE]}"""
internal const val AI_TEST_SAVED = """{"status":"READY","lastCheckOutcome":null,"analysisId":7,"matchesCurrentPortfolio":true,"lastSucceededAt":"2026-11-04T00:00:00Z","lastFailedAt":null,"failureCode":null,"changeReason":null,"analysis":$AI_TEST_ANALYSIS}"""
