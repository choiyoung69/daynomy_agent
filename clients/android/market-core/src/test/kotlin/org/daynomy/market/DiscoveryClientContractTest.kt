package org.daynomy.market

import java.io.IOException
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.test.runTest
import org.junit.Assert.*
import org.junit.Test

/** Original newslist/api.ts and newsdetail/api.ts contracts, independent of implementation. */
class DiscoveryClientContractTest {
    @Test fun defaultListUsesOneBasedPageSixItemsAndOmitsAllCategory() = runTest {
        val transport = RecordingTransport(discoveryPage())
        NewsClient(transport).list()
        assertEquals(listOf("/api/news?page=1&size=6"), transport.paths)
    }

    @Test fun categoryPageAndAllMetadataPreserveServerOrder() = runTest {
        val transport = RecordingTransport(discoveryPage("$DISCOVERY_ROW,${DISCOVERY_ROW.replace("\"id\":2", "\"id\":1")}", page = 2))
        val result = NewsClient(transport).list(NewsCategory.STOCK, 2, 6)
        assertEquals("/api/news?page=2&size=6&category=STOCK", transport.paths.single())
        assertEquals(listOf(2L, 1L), result.items.map { it.id })
        assertEquals(2, result.page); assertEquals(6, result.size)
        assertEquals(3, result.totalPages); assertEquals(13L, result.totalElements); assertTrue(result.hasNext)
        assertEquals("뉴스 😀", result.items.first().title)
        assertNull(result.items.first().imageUrl); assertNull(result.items.first().publishedAt)
    }

    @Test fun emptyPageIsSuccessfulAndRetainsPageMetadata() = runTest {
        val result = NewsClient(RecordingTransport("""{"items":[],"page":99,"size":6,"totalPages":0,"totalElements":0,"hasNext":false}""")).list(page = 99)
        assertTrue(result.items.isEmpty()); assertEquals(99, result.page)
        assertEquals(0, result.totalPages); assertEquals(0L, result.totalElements); assertFalse(result.hasNext)
    }

    @Test fun allTenWebCategoriesDecodeAndUnknownCategoryFails() = runTest {
        val names = listOf("REAL_ESTATE", "DEPOSIT_SAVINGS", "STOCK", "ECONOMY", "ETF", "BOND", "PENSION", "FOREIGN_EXCHANGE", "VIRTUAL_ASSET", "GOLD")
        for (category in names) {
            val result = NewsClient(RecordingTransport(discoveryPage(DISCOVERY_ROW.replace("STOCK", category)))).list()
            assertEquals(category, result.items.single().category.name)
        }
        for (category in listOf("ALL", "UNKNOWN", "stock")) {
            expectFailure<ResponseFormatException> { NewsClient(RecordingTransport(discoveryPage(DISCOVERY_ROW.replace("STOCK", category)))).list() }
        }
    }

    @Test fun listNullableFieldsAreRequiredAndEveryRowIsValidated() = runTest {
        val badRows = listOf(DISCOVERY_ROW.replace(",\"imageUrl\":null", ""), DISCOVERY_ROW.replace(",\"publishedAt\":null", ""), DISCOVERY_ROW.replace("\"imageUrl\":null", "\"imageUrl\":12"), DISCOVERY_ROW.replace("\"publishedAt\":null", "\"publishedAt\":false"), DISCOVERY_ROW.replace("\"title\":\"뉴스 😀\"", "\"title\":null"))
        for (row in badRows) {
            expectFailure<ResponseFormatException> { NewsClient(RecordingTransport(discoveryPage("$DISCOVERY_ROW,$row"))).list() }
        }
    }

    @Test fun missingMalformedAndWrongTypedPaginationCannotBecomeEmptySuccess() = runTest {
        val valid = discoveryPage()
        val bodies = listOf("{}", "[]", "null", "broken", valid.replace("\"items\":[$DISCOVERY_ROW],", ""), valid.replace("\"items\":[$DISCOVERY_ROW]", "\"items\":{}"), valid.replace("\"page\":1", "\"page\":\"1\""), valid.replace("\"size\":6", "\"size\":6.5"), valid.replace("\"totalPages\":3,", ""), valid.replace("\"totalElements\":13", "\"totalElements\":null"), valid.replace(",\"hasNext\":true", ""), valid.replace("\"hasNext\":true", "\"hasNext\":\"true\""))
        for (body in bodies) expectFailure<ResponseFormatException> { NewsClient(RecordingTransport(body)).list() }
    }

    @Test fun newsIdsAreExactSignedLongsWithoutStockSafeIdRestriction() = runTest {
        for (id in listOf("0", "-1", "9007199254740992", "9223372036854775807", "-9223372036854775808")) {
            val result = NewsClient(RecordingTransport(discoveryPage(DISCOVERY_ROW.replace("\"id\":2", "\"id\":$id")))).list()
            assertEquals(id.toLong(), result.items.single().id)
        }
        for (id in listOf("\"2\"", "2.5", "9223372036854775808", "null", "true", "+2", "02")) {
            expectFailure<ResponseFormatException> { NewsClient(RecordingTransport(discoveryPage(DISCOVERY_ROW.replace("\"id\":2", "\"id\":$id")))).list() }
        }
    }

    @Test fun detailSingleStringSplitsNewlinesButPreservesWhitespaceParagraph() = runTest {
        val transport = RecordingTransport(DISCOVERY_DETAIL)
        val result = NewsClient(transport).detail(2)
        assertEquals(listOf("/api/news/2"), transport.paths)
        assertEquals(listOf("첫 문단", " ", "다음 문단"), result.content)
        assertEquals("2026-10-23T00:00:00Z", result.publishedAt)
        assertEquals(listOf(NewsSourceLink("출처", "https://example.com/source")), result.sources)
        assertNull(result.imageUrl); assertNull(result.imageSource)
    }

    @Test fun detailArrayAndImageAttributionArePreserved() = runTest {
        val body = DISCOVERY_DETAIL.replace("\"첫 문단\\n\\n \\n다음 문단\"", "[\"둘\",\"\",\"하나\"]").dropLast(1) + ",\"imageUrl\":\"https://example.com/image\",\"imageSource\":$DISCOVERY_IMAGE}"
        val result = NewsClient(RecordingTransport(body)).detail(2)
        assertEquals(listOf("둘", "", "하나"), result.content)
        assertEquals("https://example.com/image", result.imageUrl)
        assertEquals(NewsImageSource("Wikimedia", "https://example.com/image", "작가", "CC BY", "https://example.com/license", NewsImageSourceType.WIKIMEDIA), result.imageSource)
    }

    @Test fun detailOptionalImageUrlAllowsExplicitNullButImageSourceDoesNot() = runTest {
        val result = NewsClient(RecordingTransport(DISCOVERY_DETAIL.dropLast(1) + ",\"imageUrl\":null}")).detail(2)
        assertNull(result.imageUrl)
        expectFailure<ResponseFormatException> { NewsClient(RecordingTransport(DISCOVERY_DETAIL.dropLast(1) + ",\"imageSource\":null}")).detail(2) }
    }

    @Test fun detailRejectsNullPublishedAtMalformedContentAndMalformedSources() = runTest {
        val bodies = listOf(DISCOVERY_DETAIL.replace("\"2026-10-23T00:00:00Z\"", "null"), DISCOVERY_DETAIL.replace("\"첫 문단\\n\\n \\n다음 문단\"", "[\"good\",null]"), DISCOVERY_DETAIL.replace("\"첫 문단\\n\\n \\n다음 문단\"", "42"), DISCOVERY_DETAIL.replace("\"name\":\"출처\"", "\"name\":42"), DISCOVERY_DETAIL.replace("\"sources\":[{\"name\":\"출처\",\"url\":\"https://example.com/source\"}]", "\"sources\":null"), DISCOVERY_DETAIL.dropLast(1) + ",\"imageSource\":${DISCOVERY_IMAGE.replace("WIKIMEDIA", "UNKNOWN")}}", DISCOVERY_DETAIL.dropLast(1) + ",\"imageSource\":${DISCOVERY_IMAGE.replace("\"author\":\"작가\",", "")}}")
        for (body in bodies) expectFailure<ResponseFormatException> { NewsClient(RecordingTransport(body)).detail(2) }
    }

    @Test fun unknownFieldsAndEmptySourceListAreAllowed() = runTest {
        val body = DISCOVERY_DETAIL.replace("[{\"name\":\"출처\",\"url\":\"https://example.com/source\"}]", "[]").dropLast(1) + ",\"future\":{\"flag\":true}}"
        assertTrue(NewsClient(RecordingTransport(body)).detail(2).sources.isEmpty())
        assertEquals(1, NewsClient(RecordingTransport(discoveryPage().dropLast(1) + ",\"future\":true}")).list().items.size)
    }

    @Test fun invalidPageAndMissingDetailPropagateServerErrorsWithoutRetry() = runTest {
        val failure = ApiException(400, "INVALID_REQUEST", "bad page")
        val transport = RecordingTransport("").apply { this.failure = failure }
        assertSame(failure, expectFailure<ApiException> { NewsClient(transport).list(page = 0, size = 101) })
        assertEquals(listOf("/api/news?page=0&size=101"), transport.paths)
        val missing = ApiException(404, "NEWS_NOT_FOUND", "not found")
        transport.failure = missing
        assertSame(missing, expectFailure<ApiException> { NewsClient(transport).detail(-1) })
        assertEquals("/api/news/-1", transport.paths.last())
    }

    @Test fun transportAndCancellationFailuresPreserveIdentity() = runTest {
        for (failure in listOf(IOException("offline"), CancellationException("cancel"))) {
            val transport = RecordingTransport("").apply { this.failure = failure }
            assertSame(failure, expectFailure<Exception> { NewsClient(transport).list() })
            assertSame(failure, expectFailure<Exception> { NewsClient(transport).detail(2) })
            assertEquals(2, transport.paths.size)
        }
    }
}

internal const val DISCOVERY_ROW = """{"id":2,"title":"뉴스 😀","category":"STOCK","imageUrl":null,"publishedAt":null}"""
internal const val DISCOVERY_DETAIL = """{"id":2,"title":"뉴스 😀","category":"STOCK","publishedAt":"2026-10-23T00:00:00Z","content":"첫 문단\n\n \n다음 문단","sources":[{"name":"출처","url":"https://example.com/source"}]}"""
internal const val DISCOVERY_IMAGE = """{"name":"Wikimedia","url":"https://example.com/image","author":"작가","license":"CC BY","licenseUrl":"https://example.com/license","type":"WIKIMEDIA"}"""
internal fun discoveryPage(items: String = DISCOVERY_ROW, page: Int = 1) = """{"items":[$items],"page":$page,"size":6,"totalPages":3,"totalElements":13,"hasNext":true}"""
