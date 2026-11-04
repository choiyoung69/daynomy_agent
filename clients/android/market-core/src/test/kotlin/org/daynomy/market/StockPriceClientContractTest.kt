package org.daynomy.market

import java.math.BigDecimal
import java.io.IOException
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.test.runTest
import org.junit.Assert.*
import org.junit.Test

class StockPriceClientContractTest {
    @Test fun latestUsesExactIdPathWithoutQueryOrOtherRequests() = runTest {
        val transport = RecordingTransport(PRICE_ROW)
        StockPriceClient(transport).latest(9007199254740991L)
        assertEquals(listOf("/api/stocks/9007199254740991/price"), transport.paths)
    }
    @Test fun invalidRequestedIdsFailBeforeNetwork() = runTest {
        val transport = RecordingTransport(PRICE_ROW)
        for (id in listOf(0L, -1L, 9007199254740992L, Long.MAX_VALUE)) {
            expectFailure<IllegalArgumentException> { StockPriceClient(transport).latest(id) }
        }
        assertTrue(transport.paths.isEmpty())
    }
    @Test fun rawDecimalTokensPreserveValueWithoutBinaryFloatOrForcedRounding() = runTest {
        for (token in listOf("12345678901234567.1234", "0.1000", "1.25e2", "0", "-1", "0.00000001")) {
            val value = StockPriceClient(RecordingTransport(PRICE_ROW.replace("71000.1250", token))).latest(1)
            assertEquals("Exact decimal $token", 0, BigDecimal(token).compareTo(value.closePrice))
        }
    }
    @Test fun arbitraryDateStringsRemainVerbatimAndUnknownFieldsAreAllowed() = runTest {
        for (date in listOf("2026-02-30", "2024-02-29", "2026-10-23", "", "not-a-date")) {
            val body = PRICE_ROW.replace("2026-10-23", date).dropLast(1) + ",\"extra\":[1,2]}"
            assertEquals(date, StockPriceClient(RecordingTransport(body)).latest(1).baseDate)
        }
    }
    @Test fun zeroAndNegativeRemainValidAtApiLayer() = runTest {
        for (token in listOf("0", "-1")) assertEquals(0, BigDecimal(token).compareTo(StockPriceClient(RecordingTransport(PRICE_ROW.replace("71000.1250", token))).latest(1).closePrice))
    }
    @Test fun nonNumericAndNonFinitePriceTokensAreRejected() = runTest {
        for (token in listOf("\"71000.1250\"", "null", "true", "[]", "{}", "1e400", "NaN", "Infinity", "-Infinity")) {
            expectFailure<ResponseFormatException> { StockPriceClient(RecordingTransport(PRICE_ROW.replace("71000.1250", token))).latest(1) }
        }
    }
    @Test fun priceRequiresTypedFieldsAndObjectEnvelope() = runTest {
        for (body in listOf("", "no-json", "null", "[]", "{}")) expectFailure<ResponseFormatException> { StockPriceClient(RecordingTransport(body)).latest(1) }
        for ((field, value) in listOf("assetId" to "1", "assetCode" to "\"005930\"", "name" to "\"삼성전자\"", "baseDate" to "\"2026-10-23\"", "closePrice" to "71000.1250")) {
            for (replacement in listOf("null", "true", "[]", "{}")) {
                expectFailure<ResponseFormatException> { StockPriceClient(RecordingTransport(PRICE_ROW.replace("\"$field\":$value", "\"$field\":$replacement"))).latest(1) }
            }
            expectFailure<ResponseFormatException> { StockPriceClient(RecordingTransport(PRICE_ROW.replace("\"$field\":$value,", ""))).latest(1) }
        }
        for (field in listOf("assetCode", "name", "baseDate")) {
            val old = when(field) { "assetCode" -> "005930"; "name" -> "삼성전자"; else -> "2026-10-23" }
            expectFailure<ResponseFormatException> { StockPriceClient(RecordingTransport(PRICE_ROW.replace("\"$field\":\"$old\"", "\"$field\":123"))).latest(1) }
        }
    }
    @Test fun responseIdIsExactPositiveSafeIntegralNumberButNeedNotMatchRequestedId() = runTest {
        for ((token, expected) in listOf("2" to 2L, "1.0" to 1L, "1e0" to 1L, "9007199254740991" to 9007199254740991L)) {
            assertEquals(expected, StockPriceClient(RecordingTransport(PRICE_ROW.replace("\"assetId\":1", "\"assetId\":$token"))).latest(1).assetId)
        }
        for (token in listOf("0", "-1", "1.5", "\"1\"", "9007199254740992", "9007199254740991.1", "1.0000000000000001")) {
            expectFailure<ResponseFormatException> { StockPriceClient(RecordingTransport(PRICE_ROW.replace("\"assetId\":1", "\"assetId\":$token"))).latest(1) }
        }
    }
    @Test fun priceCurrencyFallbackHandlesMissingNullUnknownAndInvalidType() = runTest {
        for ((code, expected) in listOf("AAPL.US" to Currency.USD, "AAPL.us" to Currency.KRW, "005930" to Currency.KRW)) {
            for (token in listOf("null", "\"UNKNOWN\"", "\"\"", "12", "false", "[]", "{}")) {
                assertEquals(expected, StockPriceClient(RecordingTransport(PRICE_ROW.replace("005930", code).replace("\"KRW\"", token))).latest(1).currency)
            }
            assertEquals(expected, StockPriceClient(RecordingTransport(PRICE_ROW.replace("005930", code).replace(",\"currency\":\"KRW\"", ""))).latest(1).currency)
        }
        assertEquals(Currency.KRW, StockPriceClient(RecordingTransport(PRICE_ROW.replace("005930", "AAPL.US"))).latest(1).currency)
        assertEquals(Currency.USD, StockPriceClient(RecordingTransport(PRICE_ROW.replace("\"KRW\"", "\"USD\""))).latest(1).currency)
    }
    @Test fun failuresIncludingCancellationAreNotRemappedToMalformedPayload() = runTest {
        val transport = RecordingTransport("")
        for (failure in listOf(CancellationException("cancel"), IOException("offline"), ApiException(404, "STOCK_PRICE_NOT_FOUND", "missing"))) {
            transport.failure = failure
            assertSame(failure, expectFailure<Exception> { StockPriceClient(transport).latest(1) })
        }
    }
}
