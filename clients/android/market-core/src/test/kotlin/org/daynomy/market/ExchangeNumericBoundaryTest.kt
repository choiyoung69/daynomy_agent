package org.daynomy.market

import java.math.BigDecimal
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Test

/** Additive independent-review oracle: original JS Number underflow is not positive. */
class ExchangeNumericBoundaryTest {
    @Test fun javascriptUnderflowFailsButSmallestPositiveRepresentableNumberSurvives() = runTest {
        expectFailure<ResponseFormatException> {
            ExchangeRateClient(RecordingTransport("""{"baseDate":"x","rate":1e-400}""")).quote("x")
        }
        val accepted = ExchangeRateClient(RecordingTransport("""{"baseDate":"x","rate":5e-324}""")).quote("x")
        assertEquals(BigDecimal("5e-324"), accepted.rate)
    }
}
