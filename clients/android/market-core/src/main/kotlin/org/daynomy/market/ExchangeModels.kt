package org.daynomy.market

import java.math.BigDecimal

data class ExchangeRate(val baseDate: String, val rate: BigDecimal)
interface ExchangeRateSource { suspend fun quote(date: String): ExchangeRate }
data class ExchangeUiState(val date: String = "", val quote: LoadState<ExchangeRate> = LoadState.Idle)
