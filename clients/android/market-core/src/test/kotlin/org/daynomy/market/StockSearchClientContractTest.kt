package org.daynomy.market

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.test.runTest
import okhttp3.HttpUrl.Companion.toHttpUrl
import org.junit.Assert.*
import org.junit.Test
import java.io.IOException

class StockSearchClientContractTest {
    @Test fun koreanSearchEncodesExactlyOneUntrimmedQueryAndOmitsCountry() = runTest {
        val transport = RecordingTransport("""{"stocks":[]}""")
        val query = "  삼성 & ETF+%_!?#  "
        assertEquals(emptyList<Stock>(), StockSearchClient(transport).search(query, Country.KR))
        val url = ("http://localhost" + transport.paths.single()).toHttpUrl()
        assertEquals("/api/stocks", url.encodedPath)
        assertEquals(setOf("q"), url.queryParameterNames)
        assertEquals(listOf(query), url.queryParameterValues("q"))
        assertNull(url.fragment)
    }
    @Test fun usSearchAddsCountryAndPreservesUnicode() = runTest {
        val transport = RecordingTransport("""{"stocks":[]}""")
        StockSearchClient(transport).search("AAPL😀 e\u0301", Country.US)
        val url = ("http://localhost" + transport.paths.single()).toHttpUrl()
        assertEquals(setOf("q", "country"), url.queryParameterNames)
        assertEquals("AAPL😀 e\u0301", url.queryParameter("q"))
        assertEquals(listOf("US"), url.queryParameterValues("country"))
    }
    @Test fun decodesEveryMarketCategoryAndPreservesOrderDuplicatesAndLength() = runTest {
        val rows = (0..20).map { index ->
            SEARCH_ROW.replace("\"KOSPI\"", "\"${Market.entries[index % 7]}\"")
                .replace("\"STOCK\"", if (index % 2 == 0) "\"STOCK\"" else "\"ETF\"")
        }
        val result = StockSearchClient(RecordingTransport("{\"stocks\":[${rows.joinToString(",")}],\"extra\":true}")).search("x", Country.KR)
        assertEquals(21, result.size)
        result.forEachIndexed { index, item ->
            assertEquals(1L, item.assetId)
            assertEquals(Market.entries[index % 7], item.market)
            assertEquals(if (index % 2 == 0) Category.STOCK else Category.ETF, item.category)
            assertEquals("삼성전자", item.name)
        }
    }
    @Test fun numericIntegralIdsIncludingDecimalAndExponentAreAcceptedExactly() = runTest {
        for ((token, expected) in listOf("1" to 1L, "1.0" to 1L, "1e0" to 1L, "9007199254740991" to 9007199254740991L)) {
            val body = "{\"stocks\":[${SEARCH_ROW.replace("\"assetId\":1", "\"assetId\":$token")}] }"
            assertEquals(expected, StockSearchClient(RecordingTransport(body)).search("x", Country.KR).single().assetId)
        }
    }
    @Test fun invalidIdsAreRejectedWithoutDoubleRoundingOrStringCoercion() = runTest {
        for (token in listOf("0", "-1", "1.5", "\"1\"", "null", "true", "9007199254740992", "9007199254740993", "9007199254740991.1", "1.0000000000000001", "1e400")) {
            val body = "{\"stocks\":[${SEARCH_ROW.replace("\"assetId\":1", "\"assetId\":$token")}] }"
            expectFailure<ResponseFormatException> { StockSearchClient(RecordingTransport(body)).search("x", Country.KR) }
        }
    }
    @Test fun malformedEnvelopesAndRowsFailTheWholeResponse() = runTest {
        val invalid = listOf("null", "[]", "{}", "{\"stocks\":null}", "{\"stocks\":{}}", "{\"stocks\":[null]}", "{\"stocks\":[\"x\"]}", "{\"stocks\":[$SEARCH_ROW,{}]}", "not-json", "")
        for (body in invalid) expectFailure<ResponseFormatException> { StockSearchClient(RecordingTransport(body)).search("x", Country.KR) }
    }
    @Test fun mandatoryFieldsAreStrictWhileEmptyStringsAndUnknownPropertiesAreAllowed() = runTest {
        val valid = SEARCH_ROW.replace("\"005930\"", "\"\"").replace("\"삼성전자\"", "\"\"").dropLast(1) + ",\"extra\":{\"x\":1}}"
        val item = StockSearchClient(RecordingTransport("{\"stocks\":[$valid]}")).search("x", Country.KR).single()
        assertEquals("", item.assetCode)
        assertEquals("", item.name)
        for ((field, value) in listOf("assetId" to "1", "assetCode" to "\"005930\"", "name" to "\"삼성전자\"", "category" to "\"STOCK\"", "market" to "\"KOSPI\"")) {
            for (replacement in listOf("null", "123", "true", "[]", "{}")) {
                if (field == "assetId" && replacement == "123") continue
                val body = SEARCH_ROW.replace("\"$field\":$value", "\"$field\":$replacement")
                expectFailure<ResponseFormatException> { StockSearchClient(RecordingTransport("{\"stocks\":[$body]}")).search("x", Country.KR) }
            }
            val missing = SEARCH_ROW.replace("\"$field\":$value,", "")
            expectFailure<ResponseFormatException> { StockSearchClient(RecordingTransport("{\"stocks\":[$missing]}")).search("x", Country.KR) }
        }
    }
    @Test fun enumValuesAndLiteralMarketTypeAreEnforcedAsDocumentedAndroidDifference() = runTest {
        for (row in listOf(SEARCH_ROW.replace("\"STOCK\"", "\"BOND\""), SEARCH_ROW.replace("\"KOSPI\"", "\"OTC\""), SEARCH_ROW.replace("\"KOSPI\"", "[\"KOSPI\"]"))) {
            expectFailure<ResponseFormatException> { StockSearchClient(RecordingTransport("{\"stocks\":[$row]}")).search("x", Country.KR) }
        }
    }
    @Test fun malformedCurrencyUsesDocumentedCodeFallbackAndExplicitCurrencyWins() = runTest {
        for ((code, expected) in listOf("AAPL.US" to Currency.USD, "AAPL.us" to Currency.KRW, "005930" to Currency.KRW)) {
            for (currency in listOf("null", "\"UNKNOWN\"", "\"\"", "12", "true", "[]", "{}")) {
                val row = SEARCH_ROW.replace("005930", code).replace("\"KRW\"", currency)
                assertEquals(expected, StockSearchClient(RecordingTransport("{\"stocks\":[$row]}")).search("x", Country.KR).single().currency)
            }
            val missing = SEARCH_ROW.replace("005930", code).replace(",\"currency\":\"KRW\"", "")
            assertEquals(expected, StockSearchClient(RecordingTransport("{\"stocks\":[$missing]}")).search("x", Country.KR).single().currency)
        }
        val explicit = SEARCH_ROW.replace("005930", "AAPL.US")
        assertEquals(Currency.KRW, StockSearchClient(RecordingTransport("{\"stocks\":[$explicit]}")).search("x", Country.KR).single().currency)
    }
    @Test fun cancellationAndTransportAndApiFailuresRemainTransparent() = runTest {
        val transport = RecordingTransport("")
        for (failure in listOf(CancellationException("cancel"), IOException("offline"), ApiException(400, "INVALID_REQUEST", "invalid"))) {
            transport.failure = failure
            val actual = expectFailure<Exception> { StockSearchClient(transport).search("x", Country.KR) }
            assertSame(failure, actual)
        }
    }
}
