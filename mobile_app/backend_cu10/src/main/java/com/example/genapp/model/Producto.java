package com.example.genapp.model;

import jakarta.persistence.*;
import lombok.Data;
import lombok.Getter;
import lombok.Setter;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;
import lombok.experimental.SuperBuilder;
import java.util.*;
import com.fasterxml.jackson.annotation.*;

@Entity
@Data
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@SuperBuilder
@JsonIdentityInfo(
    generator = ObjectIdGenerators.PropertyGenerator.class,
    property = "id",
    scope = Producto.class
)
public class Producto {

        @Id
            @GeneratedValue(strategy = GenerationType.IDENTITY)
        private Long id;
        private String nombre;
        private Double precio;


    @OneToMany(mappedBy = "producto", cascade = CascadeType.ALL, orphanRemoval = true, fetch = FetchType.LAZY)
    @JsonIgnoreProperties(value = {"producto", "hibernateLazyInitializer", "handler"}, allowSetters = true)
    private List<PedidoProducto> pedidoproducto = new ArrayList<>();


}
