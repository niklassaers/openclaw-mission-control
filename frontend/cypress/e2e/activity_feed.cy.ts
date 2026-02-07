/// <reference types="cypress" />

describe("/activity feed", () => {
  const apiBase = "**/api/v1";

  function stubStreamEmpty() {
    // Return a minimal SSE response that ends immediately.
    cy.intercept(
      "GET",
      `${apiBase}/activity/task-comments/stream*`,
      {
        statusCode: 200,
        headers: {
          "content-type": "text/event-stream",
        },
        body: "",
      },
    ).as("activityStream");
  }

  function isSignedOutView(): Cypress.Chainable<boolean> {
    return cy
      .get("body")
      .then(($body) => $body.text().toLowerCase().includes("sign in to view the feed"));
  }

  it("happy path: renders task comment cards", () => {
    cy.intercept("GET", `${apiBase}/activity/task-comments*`, {
      statusCode: 200,
      body: {
        items: [
          {
            id: "c1",
            message: "Hello world",
            agent_name: "Kunal",
            agent_role: "QA 2",
            board_id: "b1",
            board_name: "Testing",
            task_id: "t1",
            task_title: "CI hardening",
            created_at: "2026-02-07T00:00:00Z",
          },
          {
            id: "c2",
            message: "Second comment",
            agent_name: "Riya",
            agent_role: "QA",
            board_id: "b1",
            board_name: "Testing",
            task_id: "t2",
            task_title: "Coverage policy",
            created_at: "2026-02-07T00:01:00Z",
          },
        ],
      },
    }).as("activityList");

    stubStreamEmpty();

    cy.visit("/activity", {
      onBeforeLoad(win: Window) {
        win.localStorage.clear();
      },
    });

    isSignedOutView().then((signedOut) => {
      if (signedOut) {
        // In secretless CI (no Clerk), the SignedOut UI is expected and no API calls should happen.
        cy.contains(/sign in to view the feed/i).should("be.visible");
        return;
      }

      cy.wait("@activityList");

      cy.contains(/live feed/i).should("be.visible");
      cy.contains("CI hardening").should("be.visible");
      cy.contains("Coverage policy").should("be.visible");
      cy.contains("Hello world").should("be.visible");
    });
  });

  it("empty state: shows waiting message when no items", () => {
    cy.intercept("GET", `${apiBase}/activity/task-comments*`, {
      statusCode: 200,
      body: { items: [] },
    }).as("activityList");

    stubStreamEmpty();

    cy.visit("/activity");

    isSignedOutView().then((signedOut) => {
      if (signedOut) {
        cy.contains(/sign in to view the feed/i).should("be.visible");
        return;
      }

      cy.wait("@activityList");
      cy.contains(/waiting for new comments/i).should("be.visible");
    });
  });

  it("error state: shows failure UI when API errors", () => {
    cy.intercept("GET", `${apiBase}/activity/task-comments*`, {
      statusCode: 500,
      body: { detail: "boom" },
    }).as("activityList");

    stubStreamEmpty();

    cy.visit("/activity");

    isSignedOutView().then((signedOut) => {
      if (signedOut) {
        cy.contains(/sign in to view the feed/i).should("be.visible");
        return;
      }

      cy.wait("@activityList");

      // UI uses query.error.message or fallback.
      cy.contains(/unable to load feed|boom/i).should("be.visible");
    });
  });
});
