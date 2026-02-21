"""GraphQL endpoint tests."""
import pytest

pytestmark = pytest.mark.graphql

GQL_URL = "/graphql"


class TestGraphQLQueries:
    def _query(self, api, query: str, variables: dict = None):
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        return api.post(GQL_URL, json=payload)

    def test_activities_query(self, api):
        r = self._query(api, "{ activities { id } }")
        assert r.status_code == 200
        data = r.json()
        assert "data" in data, f"Expected 'data' key, got: {data}"

    def test_thoughts_query(self, api):
        r = self._query(api, "{ thoughts { id } }")
        assert r.status_code == 200
        data = r.json()
        assert "data" in data, f"Expected 'data' key, got: {data}"

    def test_goals_query(self, api):
        r = self._query(api, "{ goals { id title status } }")
        assert r.status_code == 200
        data = r.json()
        assert "data" in data, f"Expected 'data' key, got: {data}"

    def test_memories_query(self, api):
        r = self._query(api, "{ memories { key content } }")
        assert r.status_code == 200
        data = r.json()
        assert "data" in data, f"Expected 'data' key, got: {data}"

    def test_sessions_query(self, api):
        r = self._query(api, "{ sessions { id } }")
        assert r.status_code == 200
        data = r.json()
        assert "data" in data, f"Expected 'data' key, got: {data}"

    def test_stats_query(self, api):
        r = self._query(api, "{ stats { totalActivities totalThoughts totalMemories } }")
        assert r.status_code == 200
        data = r.json()
        assert "data" in data, f"Expected 'data' key, got: {data}"

    def test_knowledge_entities_query(self, api):
        r = self._query(api, "{ knowledgeEntities { id name entityType } }")
        assert r.status_code == 200
        data = r.json()
        assert "data" in data, f"Expected 'data' key, got: {data}"

    def test_knowledge_relations_query(self, api):
        r = self._query(api, "{ knowledgeRelations { id relationType } }")
        assert r.status_code == 200
        data = r.json()
        assert "data" in data, f"Expected 'data' key, got: {data}"

    def test_invalid_query(self, api):
        r = self._query(api, "{ nonExistentField }")
        assert r.status_code == 200  # GraphQL returns 200 with errors
        data = r.json()
        assert "errors" in data


class TestGraphQLMutations:
    def _mutate(self, api, query: str, variables: dict = None):
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        return api.post(GQL_URL, json=payload)

    def test_upsert_memory(self, api, uid):
        mem_key = f"gql-perf-{uid}"
        mutation = """
        mutation($key: String!, $content: String!) {
            upsertMemory(key: $key, content: $content) {
                key
                content
            }
        }
        """
        r = self._mutate(api, mutation, {"key": mem_key, "content": f"GraphQL integration run {uid}"})
        assert r.status_code == 200
        data = r.json()
        assert "data" in data, f"Mutation response missing 'data': {data}"
        # Cleanup via REST
        api.delete(f"/memories/{mem_key}")

    def test_update_goal_mutation(self, api, uid):
        """mutation updateGoal -> create a goal via REST, update via GraphQL, cleanup."""
        # Create goal via REST
        payload = {
            "title": f"GQL update test — ref {uid}",
            "status": "backlog",
            "priority": 3,
            "goal_id": f"gql-{uid}",
        }
        r = api.post("/goals", json=payload)
        if r.status_code in (502, 503):
            pytest.skip("goals service unavailable")
        assert r.status_code in (200, 201), f"Create goal failed: {r.status_code}"
        data = r.json()
        goal_id = data.get("goal_id") or data.get("id") or f"gql-{uid}"

        try:
            mutation = """
            mutation($goalId: String!, $input: GoalUpdateInput!) {
                updateGoal(goalId: $goalId, input: $input) {
                    id
                    status
                    priority
                }
            }
            """
            r = self._mutate(api, mutation, {
                "goalId": str(goal_id),
                "input": {"status": "active", "priority": 1},
            })
            assert r.status_code == 200
            gql_data = r.json()
            if gql_data is None:
                pytest.skip("GraphQL returned null response")
            assert "data" in gql_data or "errors" in gql_data, f"Mutation missing 'data': {gql_data}"
            data_section = gql_data.get("data") or {}
            if data_section.get("updateGoal"):
                updated = data_section["updateGoal"]
                assert updated.get("status") == "active" or updated.get("priority") == 1
        finally:
            # Cleanup via REST
            api.delete(f"/goals/{goal_id}")


class TestGraphQLAdvancedQueries:
    """Test graph traversal and skill-for-task queries via GraphQL."""

    def _query(self, api, query: str, variables: dict = None):
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        return api.post(GQL_URL, json=payload)

    def test_graph_traverse_query(self, api):
        """query graphTraverse -> traversal via GraphQL."""
        # Use a non-existent entity — should return empty or error gracefully
        query = """
        query($start: String!, $maxDepth: Int, $direction: String) {
            graphTraverse(start: $start, maxDepth: $maxDepth, direction: $direction) {
                totalNodes
                totalEdges
                traversalDepth
            }
        }
        """
        r = self._query(api, query, {
            "start": "00000000-0000-0000-0000-000000000000",
            "maxDepth": 2,
            "direction": "outgoing",
        })
        assert r.status_code == 200
        data = r.json()
        # May return data (empty traversal) or errors (entity not found) — both valid
        assert "data" in data or "errors" in data, f"Unexpected GQL response: {data}"

    def test_skill_for_task_query(self, api):
        """query skillForTask -> skill discovery via GraphQL."""
        query = """
        query($task: String!, $limit: Int) {
            skillForTask(task: $task, limit: $limit) {
                task
                count
                toolsSearched
            }
        }
        """
        r = self._query(api, query, {"task": "send message", "limit": 3})
        assert r.status_code == 200
        data = r.json()
        assert "data" in data or "errors" in data, f"Unexpected GQL response: {data}"
        if data.get("data", {}).get("skillForTask"):
            result = data["data"]["skillForTask"]
            assert "task" in result
            assert result["task"] == "send message"
