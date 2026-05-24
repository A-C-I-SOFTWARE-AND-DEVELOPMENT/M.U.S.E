package com.aci.hermes.data.network

import com.aci.hermes.util.LogBuffer
import kotlinx.coroutines.runBlocking
import okhttp3.OkHttpClient
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.util.concurrent.TimeUnit

/**
 * Drives the tester against an in-process MockWebServer so the error
 * mapping is exercised against real HTTP responses, not stubbed-out
 * helper return values.
 *
 * Mapping under test:
 *   * 401/403 → InvalidKey
 *   * 402 / "credit"/"insufficient_quota" / "payment_required" → PaymentRequired
 *   * 404 → ModelNotFound
 *   * 429 → RateLimited
 *   * 5xx → ProviderOutage
 *   * 2xx with empty assistant text → Unknown
 *   * 2xx with assistant text → Success
 */
class DirectApiTesterTest {

    private lateinit var server: MockWebServer
    private lateinit var http: OkHttpClient
    private lateinit var tester: DirectApiTester

    @Before
    fun setUp() {
        server = MockWebServer()
        server.start()
        // Short timeouts so the test class can't hang locally either.
        http = OkHttpClient.Builder()
            .connectTimeout(2, TimeUnit.SECONDS)
            .readTimeout(2, TimeUnit.SECONDS)
            .callTimeout(5, TimeUnit.SECONDS)
            .build()
        tester = DirectApiTester(http = http, logBuffer = LogBuffer(), callTimeoutMillis = 4_000)
    }

    @After
    fun tearDown() {
        server.shutdown()
    }

    private fun baseUrl(): String = server.url("/v1").toString().trimEnd('/')

    private suspend fun run(): DirectTestResult = tester.run(
        baseUrl = baseUrl(),
        apiKey = "sk-test",
        model = "openai/gpt-4o-mini",
        providerLabel = "TestProvider"
    )

    @Test
    fun `401 on models stage maps to InvalidKey`() = runBlocking {
        server.enqueue(MockResponse().setResponseCode(401).setBody("{\"error\":\"bad key\"}"))
        val result = run()
        assertTrue("Expected InvalidKey, got $result", result is DirectTestResult.InvalidKey)
    }

    @Test
    fun `403 on models stage maps to InvalidKey`() = runBlocking {
        server.enqueue(MockResponse().setResponseCode(403))
        val result = run()
        assertTrue("Expected InvalidKey, got $result", result is DirectTestResult.InvalidKey)
    }

    @Test
    fun `402 on models stage maps to PaymentRequired`() = runBlocking {
        server.enqueue(MockResponse().setResponseCode(402))
        val result = run()
        assertTrue("Expected PaymentRequired, got $result", result is DirectTestResult.PaymentRequired)
    }

    @Test
    fun `insufficient_quota body maps to PaymentRequired even with 400`() = runBlocking {
        server.enqueue(
            MockResponse()
                .setResponseCode(400)
                .setBody("{\"error\":{\"code\":\"insufficient_quota\",\"message\":\"x\"}}")
        )
        val result = run()
        assertTrue("Expected PaymentRequired, got $result", result is DirectTestResult.PaymentRequired)
    }

    @Test
    fun `404 on models stage maps to ModelNotFound`() = runBlocking {
        server.enqueue(MockResponse().setResponseCode(404))
        val result = run()
        assertTrue("Expected ModelNotFound, got $result", result is DirectTestResult.ModelNotFound)
    }

    @Test
    fun `429 on models stage maps to RateLimited`() = runBlocking {
        server.enqueue(MockResponse().setResponseCode(429))
        val result = run()
        assertTrue("Expected RateLimited, got $result", result is DirectTestResult.RateLimited)
    }

    @Test
    fun `503 on models stage maps to ProviderOutage`() = runBlocking {
        server.enqueue(MockResponse().setResponseCode(503))
        val result = run()
        assertTrue("Expected ProviderOutage, got $result", result is DirectTestResult.ProviderOutage)
    }

    @Test
    fun `models OK plus chat 404 maps to ModelNotFound`() = runBlocking {
        // Stage 1: models check passes.
        server.enqueue(MockResponse().setResponseCode(200).setBody("{\"data\":[]}"))
        // Stage 2: chat completion says the model doesn't exist.
        server.enqueue(MockResponse().setResponseCode(404).setBody("model not found"))
        val result = run()
        assertTrue("Expected ModelNotFound, got $result", result is DirectTestResult.ModelNotFound)
    }

    @Test
    fun `models OK plus chat 200 with assistant text maps to Success`() = runBlocking {
        server.enqueue(MockResponse().setResponseCode(200).setBody("{\"data\":[]}"))
        server.enqueue(
            MockResponse()
                .setResponseCode(200)
                .setBody(
                    """
                    {
                      "id": "x",
                      "choices": [
                        { "message": { "role": "assistant", "content": "Hermes direct mode is working." } }
                      ]
                    }
                    """.trimIndent()
                )
        )
        val result = run()
        assertTrue("Expected Success, got $result", result is DirectTestResult.Success)
        val success = result as DirectTestResult.Success
        assertEquals("Hermes direct mode is working.", success.reply)
    }

    @Test
    fun `models OK plus chat 200 with empty assistant text maps to Unknown`() = runBlocking {
        server.enqueue(MockResponse().setResponseCode(200).setBody("{\"data\":[]}"))
        server.enqueue(
            MockResponse()
                .setResponseCode(200)
                .setBody("{\"choices\":[{\"message\":{\"role\":\"assistant\",\"content\":\"\"}}]}")
        )
        val result = run()
        assertTrue("Expected Unknown, got $result", result is DirectTestResult.Unknown)
    }

    @Test
    fun `blank API key short-circuits to InvalidKey`() = runBlocking {
        // No server response should be needed — we short-circuit before any
        // HTTP call. The test would fail with "no response queued" if the
        // tester actually reached the network.
        val result = tester.run(
            baseUrl = baseUrl(),
            apiKey = "",
            model = "openai/gpt-4o-mini",
            providerLabel = "TestProvider"
        )
        assertTrue("Expected InvalidKey, got $result", result is DirectTestResult.InvalidKey)
    }

    @Test
    fun `blank model short-circuits to ModelNotFound`() = runBlocking {
        val result = tester.run(
            baseUrl = baseUrl(),
            apiKey = "sk-test",
            model = "",
            providerLabel = "TestProvider"
        )
        assertTrue("Expected ModelNotFound, got $result", result is DirectTestResult.ModelNotFound)
    }
}
