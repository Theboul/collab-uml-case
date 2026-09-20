package com.example.genapp.service;

import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import java.util.*;
import com.example.genapp.model.Pedido;
import com.example.genapp.repository.PedidoRepository;

@Service
@RequiredArgsConstructor
public class PedidoService {

    private final PedidoRepository repository;

    public List<Pedido> findAll() {
        return repository.findAll();
    }

    public Optional<Pedido> findById(Long id) {
        return repository.findById(id);
    }

    public Pedido save(Pedido e) {
        return repository.save(e);
    }

    public void delete(Long id) {
        repository.deleteById(id);
    }
}
