package org.daynomy.market

import java.io.IOException
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.test.runTest
import okhttp3.HttpUrl.Companion.toHttpUrl
import org.junit.Assert.*
import org.junit.Test

/** NewsSearchController / NewsSearchResponse / NewsListItemResponse, not the list envelope. */
class NewsSearchContractTest {
    @Test fun rawQueryIsEncodedAsOneParameterWithDefaultNewsSearchOptions() = runTest {
        val transport = RecordingTransport(searchEnvelope())
        val query = "  금리 A%_! &q=other+#/  "
        val result = NewsClient(transport).search(query)
        val url = ("https://example.invalid" + transport.paths.single()).toHttpUrl()
        assertEquals("/api/search/news", url.encodedPath)
        assertEquals(query, url.queryParameter("q"))
        assertEquals(1, url.queryParameterValues("q").size)
        assertEquals("1", url.queryParameter("page")); assertEquals("6", url.queryParameter("size"))
        assertEquals("LATEST", url.queryParameter("sort")); assertNull(url.queryParameter("category"))
        assertEquals(2L, result.items.single().id); assertTrue(result.hasNext)
    }

    @Test fun categoryPageSortAndServerOrderArePreservedWithoutClientReranking() = runTest {
        val rows = "$DISCOVERY_ROW,${DISCOVERY_ROW.replace("\"id\":2", "\"id\":1")}"
        val transport = RecordingTransport(searchEnvelope(rows, page = 2))
        val result = NewsClient(transport).search("Fed fed", NewsCategory.ETF, 2, 100, NewsSearchSort.RELEVANCE)
        val url = ("https://example.invalid" + transport.paths.single()).toHttpUrl()
        assertEquals("Fed fed", url.queryParameter("q")); assertEquals("ETF", url.queryParameter("category"))
        assertEquals("2", url.queryParameter("page")); assertEquals("100", url.queryParameter("size"))
        assertEquals("RELEVANCE", url.queryParameter("sort"))
        assertEquals(listOf(2L, 1L), result.items.map { it.id })
        assertEquals(2, result.page); assertEquals(3, result.totalPages); assertEquals(13L, result.totalElements)
    }

    @Test fun emptyAndOutOfRangePagesRemainSuccessfulAndDeriveHasNext() = runTest {
        val empty = NewsClient(RecordingTransport(searchEnvelope("", 99, 0, 0))).search("없음", page = 99)
        assertTrue(empty.items.isEmpty()); assertFalse(empty.hasNext); assertEquals(99, empty.page)
        val last = NewsClient(RecordingTransport(searchEnvelope(page = 3))).search("금리", page = 3)
        assertFalse(last.hasNext)
    }

    @Test fun queryValidationUsesRawUtf16LengthUnicodeLettersAndJavaPatternNewlines() = runTest {
        val invalid = listOf("", " \t", "%_!", "😀", "a".repeat(101), "a" + "😀".repeat(50),
            "a\nb", "a\rb", "a\u0085b", "a\u2028b", "a\u2029b")
        val transport = RecordingTransport(searchEnvelope())
        for (query in invalid) expectFailure<IllegalArgumentException> { NewsClient(transport).search(query) }
        assertTrue(transport.paths.isEmpty())
        for (query in listOf("a".repeat(100), "a" + "😀".repeat(49), "１２３", "𐐀", "\t金利\t")) {
            NewsClient(transport).search(query)
        }
        assertEquals(5, transport.paths.size)
    }

    @Test fun invalidPageAndSizeAreRejectedBeforeNetwork() = runTest {
        val transport = RecordingTransport(searchEnvelope())
        for ((page, size) in listOf(0 to 6, -1 to 6, 1 to 0, 1 to -1, 1 to 101)) {
            expectFailure<IllegalArgumentException> { NewsClient(transport).search("금리", page = page, size = size) }
        }
        assertTrue(transport.paths.isEmpty())
    }

    @Test fun malformedEnvelopesAndPaginationCannotBecomeEmptySuccess() = runTest {
        val valid = searchEnvelope()
        val bodies = listOf("{}", "[]", "null", "broken", valid.replace("\"content\"", "\"items\""),
            valid.replace("\"content\":[$DISCOVERY_ROW]", "\"content\":null"),
            valid.replace("\"page\":1", "\"page\":\"1\""), valid.replace("\"page\":1", "\"page\":0"),
            valid.replace("\"size\":6", "\"size\":0"), valid.replace("\"size\":6", "\"size\":6.5"),
            valid.replace("\"totalPages\":3", "\"totalPages\":-1"),
            valid.replace("\"totalElements\":13", "\"totalElements\":-1"),
            valid.replace("\"totalElements\":13", "\"totalElements\":null"),
            valid.replace("\"totalPages\":3,", ""))
        for (body in bodies) expectFailure<ResponseFormatException> { NewsClient(RecordingTransport(body)).search("금리") }
    }

    @Test fun everySearchRowUsesStrictExistingNewsFieldsAndExactIds() = runTest {
        val badRows = listOf(DISCOVERY_ROW.replace("\"id\":2", "\"id\":\"2\""),
            DISCOVERY_ROW.replace("\"id\":2", "\"id\":2.5"),
            DISCOVERY_ROW.replace("\"title\":\"뉴스 😀\"", "\"title\":null"),
            DISCOVERY_ROW.replace("\"category\":\"STOCK\"", "\"category\":\"UNKNOWN\""),
            DISCOVERY_ROW.replace(",\"imageUrl\":null", ""),
            DISCOVERY_ROW.replace("\"publishedAt\":null", "\"publishedAt\":false"))
        for (row in badRows) expectFailure<ResponseFormatException> { NewsClient(RecordingTransport(searchEnvelope("$DISCOVERY_ROW,$row"))).search("금리") }
        val exact = DISCOVERY_ROW.replace("\"id\":2", "\"id\":9223372036854775807")
        assertEquals(Long.MAX_VALUE, NewsClient(RecordingTransport(searchEnvelope(exact))).search("금리").items.single().id)
    }

    @Test fun errorsAndCancellationPropagateUnchangedWithoutAutomaticRetry() = runTest {
        for (failure in listOf(ApiException(400, "INVALID_REQUEST", "private"), IOException("offline"), CancellationException("cancel"))) {
            val transport = RecordingTransport("").apply { this.failure = failure }
            assertSame(failure, expectFailure<Exception> { NewsClient(transport).search("금리") })
            assertEquals(1, transport.paths.size)
        }
    }
}

private fun searchEnvelope(rows: String = DISCOVERY_ROW, page: Int = 1, pages: Int = 3, total: Long = 13) =
    """{"content":[$rows],"page":$page,"size":6,"totalPages":$pages,"totalElements":$total}"""
