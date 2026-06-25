from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations, product
from typing import Any

from topoanalyzer.model.graph import Node, TopologyGraph
from topoanalyzer.model.links import LinkParameters
from topoanalyzer.model.validation import ValidationReport
from topoanalyzer.topologies.base import TopologyBuilder


@dataclass(frozen=True)
class SlimNoCParams:
    q: int
    concentration: int = 1
    layout: str = "group"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SlimNoCParams":
        return cls(
            q=int(data["q"]),
            concentration=int(data.get("concentration", data.get("p", 1))),
            layout=str(data.get("layout", "group")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "q": self.q,
            "concentration": self.concentration,
            "layout": self.layout,
        }


class SlimNoCTopologyBuilder(TopologyBuilder):
    name = "slimnoc"
    link_classes = {"intra_0", "intra_1", "cross"}

    def validate(
        self,
        params: SlimNoCParams,
        links: LinkParameters,
    ) -> ValidationReport:
        report = ValidationReport()
        if params.q <= 1:
            report.add_error("slimnoc q must be greater than 1", q=params.q)
        delta = _delta(params.q)
        if delta is None:
            report.add_error(
                "slimnoc q must satisfy q = 4w + delta, delta in {-1, 0, 1}",
                q=params.q,
            )
        if delta not in (None, 1) and params.q > 9:
            report.add_error(
                "slimnoc delta != 1 generator search is currently limited to q <= 9",
                q=params.q,
                delta=delta,
            )
        if not _is_prime_power(params.q):
            report.add_error("slimnoc q must be a prime power", q=params.q)
        if params.concentration <= 0:
            report.add_error(
                "slimnoc concentration must be positive",
                concentration=params.concentration,
            )
        report.merge(links.validate(allowed_classes=self.link_classes))
        for idx, override in enumerate(links.overrides):
            if not isinstance(override.src, str) or not isinstance(override.dst, str):
                report.add_error(
                    "slimnoc link overrides must use router ID string endpoints",
                    override_index=idx,
                    src=override.src,
                    dst=override.dst,
                )
        return report

    def build(self, params: SlimNoCParams, links: LinkParameters) -> TopologyGraph:
        report = self.validate(params, links)
        report.raise_if_errors()

        field = FiniteField.build(params.q)
        xi = field.primitive_element()
        delta = _delta(params.q)
        if delta is None:
            raise ValueError(f"unsupported slimnoc q: {params.q}")
        x_generators, x_prime_generators = generator_sets(field, xi, delta)
        network_radix = (3 * params.q - delta) // 2
        router_count = 2 * params.q * params.q
        graph = TopologyGraph(
            name=f"slimnoc_q{params.q}_p{params.concentration}",
            topology_type=self.name,
            metadata={
                "q": params.q,
                "delta": delta,
                "field": field.to_metadata(),
                "primitive_element": xi,
                "x_generators": sorted(x_generators),
                "x_prime_generators": sorted(x_prime_generators),
                "network_radix": network_radix,
                "radix": network_radix + params.concentration,
                "concentration": params.concentration,
                "terminal_count": router_count * params.concentration,
                "router_count": router_count,
                "groups": params.q,
                "subgroups": 2 * params.q,
                "layout": params.layout,
            },
        )

        order = 0
        for subgroup_type in (0, 1):
            for subgroup in range(params.q):
                for position in range(params.q):
                    graph.add_node(
                        Node(
                            id=router_id(subgroup_type, subgroup, position),
                            kind="router",
                            metadata={
                                "subgroup_type": subgroup_type,
                                "subgroup": subgroup,
                                "group": subgroup,
                                "position": position,
                                "label": [subgroup_type, subgroup, position],
                                "coord": _layout_coord(
                                    params.layout,
                                    params.q,
                                    subgroup_type,
                                    subgroup,
                                    position,
                                ),
                                "booksim_order": order,
                            },
                        )
                    )
                    order += 1

        added: set[tuple[str, str]] = set()
        for subgroup in range(params.q):
            for b in range(params.q):
                for b_prime in range(params.q):
                    if b == b_prime:
                        continue
                    if field.sub(b, b_prime) in x_generators:
                        _add_unique_link(
                            graph,
                            links,
                            added,
                            router_id(0, subgroup, b),
                            router_id(0, subgroup, b_prime),
                            "intra_0",
                            {
                                "class": "intra_0",
                                "scope": "intra_subgroup",
                                "subgroup_type": 0,
                                "subgroup": subgroup,
                            },
                        )

            for c in range(params.q):
                for c_prime in range(params.q):
                    if c == c_prime:
                        continue
                    if field.sub(c, c_prime) in x_prime_generators:
                        _add_unique_link(
                            graph,
                            links,
                            added,
                            router_id(1, subgroup, c),
                            router_id(1, subgroup, c_prime),
                            "intra_1",
                            {
                                "class": "intra_1",
                                "scope": "intra_subgroup",
                                "subgroup_type": 1,
                                "subgroup": subgroup,
                            },
                        )

        for a in range(params.q):
            for b in range(params.q):
                for m in range(params.q):
                    c = field.sub(b, field.mul(m, a))
                    _add_unique_link(
                        graph,
                        links,
                        added,
                        router_id(0, a, b),
                        router_id(1, m, c),
                        "cross",
                        {
                            "class": "cross",
                            "scope": "inter_subgroup",
                            "left_subgroup": a,
                            "right_subgroup": m,
                        },
                    )

        return graph


@dataclass(frozen=True)
class FiniteField:
    p: int
    degree: int
    modulus: tuple[int, ...]

    @classmethod
    def build(cls, q: int) -> "FiniteField":
        p, degree = _prime_power_factor(q)
        if degree == 1:
            return cls(p=p, degree=degree, modulus=(0, 1))
        modulus = _find_irreducible_polynomial(p, degree)
        return cls(p=p, degree=degree, modulus=modulus)

    @property
    def q(self) -> int:
        return self.p**self.degree

    def add(self, left: int, right: int) -> int:
        if self.degree == 1:
            return (left + right) % self.p
        return self._from_coeffs(
            (a + b) % self.p
            for a, b in zip(self._coeffs(left), self._coeffs(right))
        )

    def neg(self, value: int) -> int:
        if self.degree == 1:
            return (-value) % self.p
        return self._from_coeffs((-coeff) % self.p for coeff in self._coeffs(value))

    def sub(self, left: int, right: int) -> int:
        return self.add(left, self.neg(right))

    def mul(self, left: int, right: int) -> int:
        if self.degree == 1:
            return (left * right) % self.p
        left_coeffs = self._coeffs(left)
        right_coeffs = self._coeffs(right)
        product_coeffs = [0] * (2 * self.degree - 1)
        for left_power, left_coeff in enumerate(left_coeffs):
            for right_power, right_coeff in enumerate(right_coeffs):
                product_coeffs[left_power + right_power] %= self.p
                product_coeffs[left_power + right_power] += left_coeff * right_coeff
                product_coeffs[left_power + right_power] %= self.p

        for power in range(len(product_coeffs) - 1, self.degree - 1, -1):
            coeff = product_coeffs[power] % self.p
            if coeff == 0:
                continue
            base_power = power - self.degree
            for idx in range(self.degree):
                product_coeffs[base_power + idx] -= coeff * self.modulus[idx]
                product_coeffs[base_power + idx] %= self.p
        return self._from_coeffs(product_coeffs[: self.degree])

    def pow(self, value: int, exponent: int) -> int:
        result = 1
        base = value
        remaining = exponent
        while remaining:
            if remaining & 1:
                result = self.mul(result, base)
            base = self.mul(base, base)
            remaining >>= 1
        return result

    def primitive_element(self) -> int:
        nonzero = set(range(1, self.q))
        for candidate in range(2, self.q):
            powers = {self.pow(candidate, exponent) for exponent in range(1, self.q)}
            if powers == nonzero:
                return candidate
        return 1

    def to_metadata(self) -> dict[str, Any]:
        return {
            "order": self.q,
            "characteristic": self.p,
            "degree": self.degree,
            "modulus": list(self.modulus),
        }

    def _coeffs(self, value: int) -> tuple[int, ...]:
        coeffs: list[int] = []
        remaining = value
        for _ in range(self.degree):
            coeffs.append(remaining % self.p)
            remaining //= self.p
        return tuple(coeffs)

    def _from_coeffs(self, coeffs: Any) -> int:
        value = 0
        scale = 1
        for coeff in coeffs:
            value += int(coeff % self.p) * scale
            scale *= self.p
        return value


def generator_sets_q_4w_plus_1(
    field: FiniteField,
    xi: int,
) -> tuple[set[int], set[int]]:
    x_generators = {
        field.pow(xi, exponent)
        for exponent in range(0, field.q - 1, 2)
    }
    x_prime_generators = {
        field.pow(xi, exponent)
        for exponent in range(1, field.q - 1, 2)
    }
    return x_generators, x_prime_generators


def generator_sets(
    field: FiniteField,
    xi: int,
    delta: int,
) -> tuple[set[int], set[int]]:
    if delta == 1:
        return generator_sets_q_4w_plus_1(field, xi)
    if field.q > 9:
        raise ValueError(
            "slimnoc generator search for delta != 1 is currently limited to q <= 9"
        )
    return _search_generator_sets(field, intra_degree=(field.q - delta) // 2)


def _search_generator_sets(
    field: FiniteField,
    *,
    intra_degree: int,
) -> tuple[set[int], set[int]]:
    elements = tuple(range(1, field.q))
    for x_generators in combinations(elements, intra_degree):
        for x_prime_generators in combinations(elements, intra_degree):
            adjacency = _candidate_adjacency(
                field,
                set(x_generators),
                set(x_prime_generators),
            )
            degrees = {len(neighbors) for neighbors in adjacency.values()}
            if degrees != {field.q + intra_degree}:
                continue
            if _has_diameter_at_most_two(adjacency):
                return set(x_generators), set(x_prime_generators)
    raise ValueError(f"no SlimNoC generator sets found for q={field.q}")


def _candidate_adjacency(
    field: FiniteField,
    x_generators: set[int],
    x_prime_generators: set[int],
) -> dict[tuple[int, int, int], set[tuple[int, int, int]]]:
    adjacency = {
        (subgroup_type, subgroup, position): set()
        for subgroup_type in (0, 1)
        for subgroup in range(field.q)
        for position in range(field.q)
    }
    for subgroup in range(field.q):
        for left in range(field.q):
            for right in range(field.q):
                if left == right:
                    continue
                if field.sub(left, right) in x_generators:
                    adjacency[(0, subgroup, left)].add((0, subgroup, right))
                    adjacency[(0, subgroup, right)].add((0, subgroup, left))
                if field.sub(left, right) in x_prime_generators:
                    adjacency[(1, subgroup, left)].add((1, subgroup, right))
                    adjacency[(1, subgroup, right)].add((1, subgroup, left))

    for a in range(field.q):
        for b in range(field.q):
            for m in range(field.q):
                c = field.sub(b, field.mul(m, a))
                adjacency[(0, a, b)].add((1, m, c))
                adjacency[(1, m, c)].add((0, a, b))
    return adjacency


def _has_diameter_at_most_two(
    adjacency: dict[tuple[int, int, int], set[tuple[int, int, int]]],
) -> bool:
    nodes = list(adjacency)
    for source in nodes:
        seen = {source}
        frontier = {source}
        for _ in range(2):
            next_frontier: set[tuple[int, int, int]] = set()
            for node in frontier:
                next_frontier.update(adjacency[node])
            frontier = next_frontier - seen
            seen.update(next_frontier)
        if len(seen) != len(nodes):
            return False
    return True


def router_id(subgroup_type: int, subgroup: int, position: int) -> str:
    return f"sn.g{subgroup_type}.a{subgroup}.b{position}"


def _add_unique_link(
    graph: TopologyGraph,
    links: LinkParameters,
    added: set[tuple[str, str]],
    src: str,
    dst: str,
    link_class: str,
    metadata: dict[str, Any],
) -> None:
    key = tuple(sorted((src, dst)))
    if key in added:
        return
    added.add(key)
    spec_ab = links.resolve(src, dst, link_class=link_class)
    spec_ba = links.resolve(dst, src, link_class=link_class)
    graph.add_bidirectional_link(src, dst, spec_ab, spec_ba, metadata=metadata)


def _layout_coord(
    layout: str,
    q: int,
    subgroup_type: int,
    subgroup: int,
    position: int,
) -> list[int]:
    if layout == "subgroup":
        return [position, subgroup_type * q + subgroup]
    if layout == "basic":
        return [subgroup * q + position, subgroup_type]
    group_side = _square_side(q)
    if group_side is not None:
        group_x = subgroup % group_side
        group_y = subgroup // group_side
        return [group_x * (2 * q) + subgroup_type * q + position, group_y]
    return [subgroup_type * q + position, subgroup]


def _square_side(value: int) -> int | None:
    side = int(value**0.5)
    if side * side == value:
        return side
    return None


def _is_prime_power(value: int) -> bool:
    try:
        _prime_power_factor(value)
    except ValueError:
        return False
    return True


def _delta(q: int) -> int | None:
    remainder = q % 4
    if remainder == 0:
        return 0
    if remainder == 1:
        return 1
    if remainder == 3:
        return -1
    return None


def _prime_power_factor(value: int) -> tuple[int, int]:
    if value <= 1:
        raise ValueError("value must be greater than one")
    for prime in range(2, value + 1):
        if not _is_prime(prime):
            continue
        degree = 0
        remaining = value
        while remaining % prime == 0:
            remaining //= prime
            degree += 1
        if remaining == 1 and degree > 0:
            return prime, degree
    raise ValueError(f"{value} is not a prime power")


def _is_prime(value: int) -> bool:
    if value < 2:
        return False
    divisor = 2
    while divisor * divisor <= value:
        if value % divisor == 0:
            return False
        divisor += 1
    return True


def _find_irreducible_polynomial(p: int, degree: int) -> tuple[int, ...]:
    for coeffs in product(range(p), repeat=degree):
        polynomial = (*coeffs, 1)
        if _is_irreducible(polynomial, p):
            return polynomial
    raise ValueError(f"no irreducible polynomial found for GF({p}^{degree})")


def _is_irreducible(polynomial: tuple[int, ...], p: int) -> bool:
    degree = len(polynomial) - 1
    for divisor_degree in range(1, degree // 2 + 1):
        for divisor_coeffs in product(range(p), repeat=divisor_degree):
            divisor = (*divisor_coeffs, 1)
            _, remainder = _poly_divmod(polynomial, divisor, p)
            if not any(remainder):
                return False
    return True


def _poly_divmod(
    dividend: tuple[int, ...],
    divisor: tuple[int, ...],
    p: int,
) -> tuple[list[int], list[int]]:
    remainder = [coeff % p for coeff in dividend]
    quotient = [0] * max(1, len(dividend) - len(divisor) + 1)
    divisor_degree = len(divisor) - 1
    divisor_lead_inv = pow(divisor[-1], -1, p)
    for idx in range(len(dividend) - len(divisor), -1, -1):
        coeff = remainder[divisor_degree + idx] * divisor_lead_inv % p
        quotient[idx] = coeff
        if coeff == 0:
            continue
        for divisor_idx, divisor_coeff in enumerate(divisor):
            remainder[idx + divisor_idx] -= coeff * divisor_coeff
            remainder[idx + divisor_idx] %= p
    while len(remainder) > 1 and remainder[-1] == 0:
        remainder.pop()
    return quotient, remainder
