package org.daynomy.market

import java.io.IOException
import java.math.BigDecimal
import java.net.URI
import java.net.URLDecoder
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.test.runTest
import org.junit.Assert.*
import org.junit.Test

/** Authored from the KB and original stocks/api.ts before this slice's implementation. */
class ExchangeClientContractTest {
    @Test fun dateIsEncodedOnceWithoutChangingUserInput() = runTest {
        val input = "2026-10-25 &한글+?"
        val transport = RecordingTransport(EXCHANGE_BODY)
        ExchangeRateClient(transport).quote(input)
        val uri = URI(transport.paths.single())
        assertEquals("/api/exchange-rates/usd-krw", uri.path)
        assertEquals(listOf("date"), uri.rawQuery.split('&').map { it.substringBefore('=') })
        assertEquals(input, URLDecoder.decode(uri.rawQuery.substringAfter('='), "UTF-8"))
    }

    @Test fun actualBaseDateAndSixDecimalRateSurviveWithoutBinaryRounding() = runTest {
        val result = ExchangeRateClient(RecordingTransport(EXCHANGE_BODY)).quote("2026-10-25")
        assertEquals("2026-10-23", result.baseDate)
        assertEquals(BigDecimal("1423.123456"), result.rate)
    }

    @Test fun originalWebRequiresOnlyBaseDateAndRateAndDoesNotParseCalendar() = runTest {
        val result = ExchangeRateClient(RecordingTransport("""{"baseDate":"not-a-calendar-date","rate":1.234567890123456789,"extra":true}""")).quote("invalid date")
        assertEquals("not-a-calendar-date", result.baseDate)
        assertEquals(BigDecimal("1.234567890123456789"), result.rate)
    }

    @Test fun validExponentNumberIsAcceptedWithoutPrecisionLoss() = runTest {
        val result = ExchangeRateClient(RecordingTransport("""{"baseDate":"x","rate":1.23456789e3}""")).quote("x")
        assertEquals(0, BigDecimal("1234.56789").compareTo(result.rate))
    }

    @Test fun missingNullAndWrongTypedFieldsAreFormatFailures() = runTest {
        for (body in listOf("{}", "[]", "null", "bad json", """{"rate":1}""", """{"baseDate":null,"rate":1}""", """{"baseDate":1,"rate":1}""", """{"baseDate":"x"}""", """{"baseDate":"x","rate":null}""", """{"baseDate":"x","rate":"1.2"}""", """{"baseDate":"x","rate":true}""")) {
            expectFailure<ResponseFormatException> { ExchangeRateClient(RecordingTransport(body)).quote("2026-10-25") }
        }
    }

    @Test fun nonPositiveAndNonFiniteRatesAreNeverSuccessfulQuotes() = runTest {
        for (number in listOf("0", "-0.0", "-1", "1e309", "NaN", "Infinity")) {
            expectFailure<ResponseFormatException> { ExchangeRateClient(RecordingTransport("""{"baseDate":"x","rate":$number}""")).quote("x") }
        }
    }

    @Test fun malformedJsonNumericGrammarCannotBeAcceptedByBigDecimal() = runTest {
        for (number in listOf("+1", "01", "1.", ".1", "1e+")) {
            expectFailure<ResponseFormatException> { ExchangeRateClient(RecordingTransport("""{"baseDate":"x","rate":$number}""")).quote("x") }
        }
    }

    @Test fun httpErrorsAndIoFailurePropagateUnchangedWithoutRetry() = runTest {
        for (failure in listOf(ApiException(400, "INVALID_EXCHANGE_RATE_DATE", "bad date"), ApiException(429, "TOO_MANY_REQUESTS", "rate limit"), IOException("offline"))) {
            val transport = RecordingTransport(EXCHANGE_BODY).apply { this.failure = failure }
            val actual = expectFailure<Exception> { ExchangeRateClient(transport).quote("1999-12-31") }
            assertSame(failure, actual)
            assertEquals(1, transport.paths.size)
        }
    }

    @Test fun cancellationIsNotConvertedToFormatOrApiFailure() = runTest {
        val cancelled = CancellationException("cancelled")
        val transport = RecordingTransport(EXCHANGE_BODY).apply { failure = cancelled }
        assertSame(cancelled, expectFailure<CancellationException> { ExchangeRateClient(transport).quote("2026-10-25") })
    }
}

internal const val EXCHANGE_BODY = """{"requestedDate":"2026-10-25","baseDate":"2026-10-23","rate":1423.123456,"baseCurrency":"USD","quoteCurrency":"KRW"}"""
