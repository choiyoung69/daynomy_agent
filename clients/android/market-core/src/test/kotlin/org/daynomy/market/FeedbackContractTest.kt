package org.daynomy.market

import java.io.IOException
import java.util.concurrent.TimeUnit
import kotlin.coroutines.Continuation
import kotlin.coroutines.resume
import kotlin.coroutines.suspendCoroutine
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.Assert.*
import org.junit.Test

/** F11 contracts authored independently against spec/android-native/feedback.md. */
@OptIn(ExperimentalCoroutinesApi::class)
class FeedbackContractTest {
    private class RecordingSession : SessionTransport {
        data class Request(val method: String, val path: String, val body: String?)
        val requests = mutableListOf<Request>()
        var failure: Throwable? = null
        override suspend fun get(pathAndQuery: String): String = error("Unexpected GET")
        override suspend fun request(method: String, path: String, jsonBody: String?): String {
            requests += Request(method, path, jsonBody)
            failure?.let { throw it }
            return ""
        }
    }

    private class ControlledSource : FeedbackSource {
        val submissions = mutableListOf<Pair<String, String>>()
        val completion = CompletableDeferred<Unit>()
        override suspend fun submit(content: String, pagePath: String) {
            submissions += content to pagePath
            completion.await()
        }
    }

    private fun json(body: String, status: Int = 200) = MockResponse()
        .setResponseCode(status).setHeader("Content-Type", "application/json").setBody(body)

    private fun csrf() = json("""{"headerName":"X-XSRF-TOKEN","token":"fixture-feedback"}""")
        .addHeader("Set-Cookie", "XSRF-TOKEN=fixture-feedback; Path=/")

    @Test fun contentLimitCountsOriginalUtf16CodeUnits() {
        for (valid in listOf("a".repeat(1000), "😀".repeat(500), "😀".repeat(499) + "ab")) {
            assertEquals(1000, valid.length)
            assertNull(feedbackContentError(valid))
        }
        for (invalid in listOf("a".repeat(1001), "😀".repeat(500) + "a", " " + "a".repeat(1000))) {
            assertEquals(1001, invalid.length)
            assertNotNull(feedbackContentError(invalid))
        }
    }

    @Test fun blankValidationUsesJavaWhitespaceAndPreservesNbsp() {
        for (blank in listOf("", " ", "\t\n\r", "\u2003", " \t\u2003\n")) {
            assertNotNull("Blank input must be rejected", feedbackContentError(blank))
        }
        for (valid in listOf("\u00a0", " \u00a0 ", "😀", " text\n")) {
            assertNull(feedbackContentError(valid))
        }
    }

    @Test fun clientRejectsInvalidContentBeforeTransportWithoutTrimming() = runTest {
        val transport = RecordingSession()
        val client = FeedbackClient(transport)
        for (content in listOf("", "\u2003\t", " " + "a".repeat(1000), "😀".repeat(500) + "a")) {
            expectFailure<Exception> { client.submit(content, "/feedback") }
        }
        assertTrue(transport.requests.isEmpty())
    }

    @Test fun pagePathHasLengthAndJavaBlankValidationButNoSlashRequirement() = runTest {
        val transport = RecordingSession()
        val client = FeedbackClient(transport)
        for (path in listOf("", " \t\u2003", "p".repeat(2049), " " + "p".repeat(2048))) {
            expectFailure<Exception> { client.submit("의견", path) }
        }
        assertTrue(transport.requests.isEmpty())
        for (path in listOf("plain-screen", "p".repeat(2048), "\u00a0")) {
            client.submit("의견", path)
            val body = Json.parseToJsonElement(transport.requests.last().body!!).jsonObject
            assertEquals(path, body.getValue("pagePath").jsonPrimitive.content)
        }
    }

    @Test fun clientPreservesRawJsonStringsAndAcceptsEmptySuccessBody() = runTest {
        val transport = RecordingSession()
        val content = "  의견 \"quoted\"\n\\ 끝 😀\u00a0  "
        val path = "  plain-screen\n  "
        FeedbackClient(transport).submit(content, path)
        val request = transport.requests.single()
        assertEquals("POST", request.method)
        assertEquals("/api/feedback", request.path)
        val body = Json.parseToJsonElement(request.body!!).jsonObject
        assertEquals(setOf("content", "pagePath"), body.keys)
        assertEquals(content, body.getValue("content").jsonPrimitive.content)
        assertEquals(path, body.getValue("pagePath").jsonPrimitive.content)
    }

    @Test fun realSessionPreparesCsrfCookieAndHeaderThenAcceptsEmpty204() = runTest {
        MockWebServer().use { server ->
            server.enqueue(csrf())
            server.enqueue(MockResponse().setResponseCode(204))
            server.start()
            FeedbackClient(SessionHttpTransport(server.url("/").toString())).submit("  의견 😀  ", "/feedback")
            val prepare = server.takeRequest(3, TimeUnit.SECONDS)!!
            assertEquals("GET", prepare.method)
            assertEquals("/api/auth/csrf", prepare.path)
            val post = server.takeRequest(3, TimeUnit.SECONDS)!!
            assertEquals("POST", post.method)
            assertEquals("/api/feedback", post.path)
            assertTrue(post.getHeader("Content-Type").orEmpty().startsWith("application/json"))
            assertEquals("fixture-feedback", post.getHeader("X-XSRF-TOKEN"))
            assertTrue(post.getHeader("Cookie").orEmpty().contains("XSRF-TOKEN=fixture-feedback"))
            val body = Json.parseToJsonElement(post.body.readUtf8()).jsonObject
            assertEquals("  의견 😀  ", body.getValue("content").jsonPrimitive.content)
            assertEquals("/feedback", body.getValue("pagePath").jsonPrimitive.content)
            assertEquals(2, server.requestCount)
        }
    }

    @Test fun realHttp403And500PropagateWithoutAutomaticReplay() = runTest {
        for ((status, code) in listOf(403 to "FORBIDDEN", 500 to "INTERNAL_SERVER_ERROR")) {
            MockWebServer().use { server ->
                server.enqueue(csrf())
                server.enqueue(json("""{"code":"$code","message":"fixture failure"}""", status))
                // A mistaken retry receives a terminal response instead of hanging this test.
                server.enqueue(json("""{"code":"$code","message":"fixture failure"}""", status))
                server.start()
                val failure = expectFailure<ApiException> {
                    FeedbackClient(SessionHttpTransport(server.url("/").toString())).submit("의견", "/feedback")
                }
                assertEquals(status, failure.status)
                assertEquals(code, failure.code)
                assertEquals(2, server.requestCount)
            }
        }
    }

    @Test fun clientPropagatesCancellationUnchanged() = runTest {
        val transport = RecordingSession()
        val cancellation = CancellationException("fixture cancellation")
        transport.failure = cancellation
        assertSame(cancellation, expectFailure<CancellationException> {
            FeedbackClient(transport).submit("의견", "/feedback")
        })
        assertEquals(1, transport.requests.size)
        val source = object : FeedbackSource {
            override suspend fun submit(content: String, pagePath: String) { throw cancellation }
        }
        val controller = FeedbackController(source, backgroundScope)
        try {
            controller.editContent("취소된 의견")
            controller.submit()
            runCurrent()
            assertEquals("취소된 의견", controller.state.value.content)
            assertNull(controller.state.value.error)
            assertFalse(controller.state.value.outcomeUnknown)
            assertFalse(controller.state.value.sent)
        } finally { controller.close() }
    }

    @Test fun controllerRejectsBlankAndOverLimitInputBeforeCallingSource() = runTest {
        val source = ControlledSource()
        val controller = FeedbackController(source, backgroundScope)
        try {
            for (content in listOf("\u2003\t", "a".repeat(1001))) {
                controller.editContent(content)
                controller.submit()
                runCurrent()
                assertEquals(content, controller.state.value.content)
                assertFalse(controller.state.value.isSubmitting)
                assertFalse(controller.state.value.sent)
                assertNotNull(controller.state.value.error)
            }
            assertTrue(source.submissions.isEmpty())
        } finally { controller.close() }
    }

    @Test fun busyStateIsSynchronousAndSuppressesDuplicateClicksAndEdits() = runTest {
        val source = ControlledSource()
        val controller = FeedbackController(source, backgroundScope)
        try {
            controller.editContent("  원문 😀  ")
            controller.submit()
            assertTrue(controller.state.value.isSubmitting)
            controller.submit()
            controller.editContent("변경")
            assertEquals("  원문 😀  ", controller.state.value.content)
            runCurrent()
            assertEquals(listOf("  원문 😀  " to "/feedback"), source.submissions)
            controller.submit()
            controller.editContent("또 변경")
            runCurrent()
            assertEquals(1, source.submissions.size)
            assertEquals("  원문 😀  ", controller.state.value.content)
        } finally { controller.close() }
    }

    @Test fun onlySuccessfulCompletionClearsDraftAndMarksSent() = runTest {
        val source = ControlledSource()
        val controller = FeedbackController(source, backgroundScope, "account-screen")
        try {
            controller.editContent("의견")
            controller.submit()
            runCurrent()
            assertEquals("의견", controller.state.value.content)
            assertFalse(controller.state.value.sent)
            assertEquals(listOf("의견" to "account-screen"), source.submissions)
            source.completion.complete(Unit)
            runCurrent()
            assertEquals("", controller.state.value.content)
            assertTrue(controller.state.value.sent)
            assertFalse(controller.state.value.isSubmitting)
            assertFalse(controller.state.value.outcomeUnknown)
            assertNull(controller.state.value.error)
        } finally { controller.close() }
    }

    @Test fun apiFailureRetainsDraftAndAllowsAnExplicitRetry() = runTest {
        var calls = 0
        val source = object : FeedbackSource {
            override suspend fun submit(content: String, pagePath: String) {
                calls++
                if (calls == 1) throw ApiException(500, "INTERNAL_SERVER_ERROR", "fixture failure")
            }
        }
        val controller = FeedbackController(source, backgroundScope)
        try {
            controller.editContent("  보존할 의견  ")
            controller.submit()
            runCurrent()
            assertEquals(1, calls)
            assertEquals("  보존할 의견  ", controller.state.value.content)
            assertNotNull(controller.state.value.error)
            assertFalse(controller.state.value.sent)
            assertFalse(controller.state.value.outcomeUnknown)
            assertFalse(controller.state.value.isSubmitting)
            controller.submit()
            runCurrent()
            assertEquals(2, calls)
            assertTrue(controller.state.value.sent)
            assertEquals("", controller.state.value.content)
        } finally { controller.close() }
    }

    @Test fun ioFailureKeepsDraftAndBlocksResendUntilExplicitReset() = runTest {
        var calls = 0
        val source = object : FeedbackSource {
            override suspend fun submit(content: String, pagePath: String) {
                calls++
                if (calls == 1) throw IOException("fixture lost response")
            }
        }
        val controller = FeedbackController(source, backgroundScope)
        try {
            controller.editContent("결과가 불명확한 의견")
            controller.submit()
            runCurrent()
            assertEquals("결과가 불명확한 의견", controller.state.value.content)
            assertTrue(controller.state.value.outcomeUnknown)
            assertNotNull(controller.state.value.error)
            assertFalse(controller.state.value.isSubmitting)
            assertFalse(controller.state.value.sent)
            controller.submit()
            runCurrent()
            assertEquals(1, calls)
            controller.editContent("다른 초안")
            controller.submit()
            runCurrent()
            assertEquals(1, calls)
            controller.reset()
            assertEquals(FeedbackUiState(), controller.state.value)
            controller.editContent("새 의견")
            controller.submit()
            runCurrent()
            assertEquals(2, calls)
            assertTrue(controller.state.value.sent)
        } finally { controller.close() }
    }

    @Test fun closeDiscardsLateNoncooperativeCompletion() = runTest {
        lateinit var completion: Continuation<Unit>
        val source = object : FeedbackSource {
            override suspend fun submit(content: String, pagePath: String) {
                suspendCoroutine<Unit> { completion = it }
            }
        }
        val controller = FeedbackController(source, backgroundScope)
        controller.editContent("닫기 전 의견")
        controller.submit()
        runCurrent()
        controller.close()
        val closedState = controller.state.value
        completion.resume(Unit)
        runCurrent()
        assertEquals(closedState, controller.state.value)
        assertFalse(controller.state.value.sent)
    }
}
